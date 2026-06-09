"""Typed, dict-compatible AD response models (ADR 0001, Stage N).

This module provides additive typed response models for Active Directory
operations. The models are JSON-serializable Pydantic models that also behave
like read-only mappings, so existing consumers that rely on legacy dictionary
access (for example ``response['success']`` or ``response['result']``) continue
to work unchanged.

Stage N scope note:
    These models are introduced additively. They do not change what
    ``python_apis.apis.ad_api.ADConnection`` methods return today; wiring the
    models into live operation envelopes with legacy mirroring is tracked
    separately (issue #19).
"""

from collections.abc import Iterator, Mapping, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

_ADResponseT = TypeVar("_ADResponseT", bound="ADResponse")


class ADResponse(BaseModel, Mapping):
    """Base AD response model that is both typed and dict-compatible.

    Subclasses gain typed attribute access while remaining usable as read-only
    mappings. Legacy consumers can continue to use dictionary-style access such
    as ``response['success']``, ``response.get('result')``, ``'key' in response``,
    ``dict(response)`` and ``**response`` without changes.

    Unknown keys provided at construction time are preserved (``extra='allow'``)
    so adapters never silently drop data.
    """

    model_config = ConfigDict(extra="allow")

    def _mapping_keys(self) -> list[str]:
        """Return the ordered key surface (declared fields then extras)."""

        keys = list(type(self).model_fields.keys())
        extra = self.model_extra or {}
        keys.extend(key for key in extra if key not in keys)
        return keys

    def __getitem__(self, key: str) -> Any:
        """Return the value for ``key`` using legacy dictionary semantics."""

        if key in type(self).model_fields:
            return getattr(self, key)
        extra = self.model_extra or {}
        if key in extra:
            return extra[key]
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        """Iterate over mapping keys (not ``(key, value)`` pairs)."""

        return iter(self._mapping_keys())

    def __len__(self) -> int:
        """Return the number of mapping keys."""

        return len(self._mapping_keys())

    def __contains__(self, key: object) -> bool:
        """Return whether ``key`` is present in the mapping surface."""

        return key in self._mapping_keys()

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serializable ``dict`` of this response."""

        return self.model_dump()

    @classmethod
    def from_legacy(cls: type[_ADResponseT], payload: Mapping[str, Any]) -> _ADResponseT:
        """Wrap a legacy response ``Mapping`` into a typed model losslessly.

        Unknown keys are preserved (``extra='allow'``), so adapting an existing
        payload and calling :meth:`to_dict` round-trips to the original data.
        """

        return cls.model_validate(dict(payload))


class ADOperationResponse(ADResponse):
    """Typed envelope for AD mutation operations.

    Mirrors the legacy mutation payload ``{'result': ..., 'success': ...}`` while
    exposing ``success`` and ``result`` as typed attributes. Both remain
    available through dictionary access for legacy consumers.
    """

    success: bool
    result: dict[str, Any] = Field(default_factory=dict)


class ADEntry(ADResponse):
    """Typed, dict-compatible representation of a single AD object.

    Used for single-object reads (for example ``ADConnection.get``). AD
    attributes are dynamic, so all values are stored as mapping entries and are
    accessible both as items (``entry['cn']``) and via ``get``.
    """


class ADSearchResponse(BaseModel, Sequence):
    """Typed, list-compatible wrapper for multi-object AD reads.

    Preserves the legacy ``list[dict]`` access pattern returned by
    ``ADConnection.search`` while wrapping each result in a typed
    :class:`ADEntry`. Supports indexing, iteration and ``len``.
    """

    model_config = ConfigDict(extra="forbid")

    entries: list[ADEntry] = Field(default_factory=list)

    def __getitem__(self, index: Any) -> Any:
        """Return the entry (or slice of entries) at ``index``."""

        return self.entries[index]

    def __iter__(self) -> Iterator[ADEntry]:  # type: ignore[override]
        """Iterate over the wrapped :class:`ADEntry` objects."""

        return iter(self.entries)

    def __len__(self) -> int:
        """Return the number of entries."""

        return len(self.entries)

    def to_list(self) -> list[dict[str, Any]]:
        """Return a plain, JSON-serializable ``list[dict]`` of the entries."""

        return [entry.to_dict() for entry in self.entries]

    @classmethod
    def from_legacy(cls, payloads: Sequence[Mapping[str, Any]]) -> "ADSearchResponse":
        """Wrap a legacy ``list[dict]`` search result into a typed model.

        Each element is wrapped in an :class:`ADEntry` without dropping keys, so
        :meth:`to_list` round-trips to the original list of dictionaries.
        """

        return cls(entries=[ADEntry.from_legacy(payload) for payload in payloads])


__all__: list[str] = [
    "ADResponse",
    "ADOperationResponse",
    "ADEntry",
    "ADSearchResponse",
]
