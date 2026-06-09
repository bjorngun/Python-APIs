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

from collections.abc import Iterator, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict


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


__all__: list[str] = [
    "ADResponse",
]
