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

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field

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

    # Optional default-factory captured from a legacy ``defaultdict`` source so
    # missing-key access can preserve the original default (for example the
    # empty-string default produced by ``ADConnection.get`` on no match).
    _missing_default_factory: Callable[[], Any] | None = PrivateAttr(default=None)

    def _mapping_keys(self) -> list[str]:
        """Return the ordered key surface (fields, computed fields, then extras)."""

        keys = list(type(self).model_fields.keys())
        keys.extend(
            key for key in type(self).model_computed_fields.keys() if key not in keys
        )
        extra = self.model_extra or {}
        keys.extend(key for key in extra if key not in keys)
        return keys

    def __getitem__(self, key: str) -> Any:
        """Return the value for ``key`` using legacy dictionary semantics.

        If this response was adapted from a ``defaultdict`` (for example the
        no-result return of ``ADConnection.get``), missing keys resolve to the
        original default instead of raising ``KeyError``.
        """

        if key in list(type(self).model_fields.keys()):
            return getattr(self, key)
        if key in list(type(self).model_computed_fields.keys()):
            return getattr(self, key)
        extra = self.model_extra or {}
        if key in extra:
            return extra[key]
        default_factory = self._missing_default_factory
        if default_factory is not None:
            return default_factory()  # pylint: disable=not-callable
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

        If ``payload`` is a ``defaultdict`` (or any mapping exposing a
        ``default_factory``), that factory is retained so missing-key access on
        the resulting model matches the legacy default behavior.
        """

        instance = cls.model_validate(dict(payload))
        # Accessing the instance's own private attribute is safe here; pylint
        # flags same-class private access through a non-``self`` reference.
        instance._missing_default_factory = getattr(  # pylint: disable=protected-access
            payload, "default_factory", None
        )
        return instance


class ADOperationResponse(ADResponse):
    """Typed envelope for AD mutation operations.

    Mirrors the legacy mutation payload ``{'result': ..., 'success': ...}`` while
    exposing ``success`` and ``result`` as typed attributes. Both remain
    available through dictionary access for legacy consumers.

    ``result`` is intentionally typed broadly (``Any``) because existing AD
    service paths return either the LDAP result mapping on success or a string
    error message on failure (for example ``{'success': False, 'result': str(e)}``).
    """

    success: bool
    result: Any = None


class ADOperationEnvelope(ADResponse):
    """Consistent operation envelope for AD service calls (ADR 0001, Stage N).

    Provides modern, structured metadata for an AD operation while mirroring the
    legacy top-level keys (``success``, ``result``, ``message``) so existing
    consumers keep working during the migration. ``result`` mirrors
    ``ldap_result`` and ``message`` mirrors ``exception_message``; the mirror
    values never diverge from their modern counterparts.

    Forward-compatible fields are included now with safe defaults so the
    envelope shape stays stable across the rollout:

    - ``error_code`` is populated by the normalized error taxonomy (issue #20).
    - ``retry_count`` / ``retried`` / ``would_retry`` / ``retry_policy`` are
      populated by retry telemetry (issue #21). ``did_retry`` is a legacy-style
      computed mirror of ``retried``.
    """

    success: bool
    operation_kind: Literal["read", "write"]
    ldap_result: Any = None
    exception_type: str | None = None
    exception_message: str | None = None
    request_context: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    retried: bool = False
    would_retry: bool = False
    retry_policy: dict[str, Any] | None = None
    error_code: str | None = None

    @computed_field
    @property
    def result(self) -> Any:
        """Legacy mirror of :attr:`ldap_result`."""

        return self.ldap_result

    @computed_field
    @property
    def message(self) -> str | None:
        """Legacy mirror of :attr:`exception_message`."""

        return self.exception_message

    @computed_field
    @property
    def did_retry(self) -> bool:
        """Telemetry mirror of :attr:`retried` (issue #21 vocabulary)."""

        return self.retried

    @classmethod
    def from_operation(  # pylint: disable=too-many-arguments
        cls,
        *,
        operation_kind: Literal["read", "write"],
        success: bool | None = None,
        ldap_result: Any = None,
        exception: BaseException | None = None,
        request_context: dict[str, Any] | None = None,
        retry_count: int = 0,
        retried: bool = False,
        would_retry: bool = False,
        retry_policy: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> "ADOperationEnvelope":
        """Build an envelope from an AD operation outcome.

        Captures the structured result of a single AD operation. When
        ``exception`` is provided, ``exception_type`` and ``exception_message``
        are derived from it and ``success`` defaults to ``False``; otherwise
        ``success`` defaults to ``True`` unless explicitly supplied.

        ``retry_count``/``retried``/``would_retry``/``retry_policy`` carry retry
        telemetry (issue #21) and ``error_code`` carries the normalized error
        taxonomy code (issue #20); all default to safe values.
        """

        exception_type: str | None = None
        exception_message: str | None = None
        if exception is not None:
            exception_type = type(exception).__name__
            exception_message = str(exception)

        if success is None:
            success = exception is None

        return cls(
            success=success,
            operation_kind=operation_kind,
            ldap_result=ldap_result,
            exception_type=exception_type,
            exception_message=exception_message,
            request_context=request_context or {},
            retry_count=retry_count,
            retried=retried,
            would_retry=would_retry,
            retry_policy=retry_policy,
            error_code=error_code,
        )

    def to_response(self, mode: str | None = None) -> dict[str, Any]:
        """Return the envelope as a dict shaped for the given compatibility mode.

        - ``legacy``/``mixed``: include legacy mirror keys (``success``,
          ``result``, ``message``) alongside modern fields.
        - ``strict``: omit legacy mirror keys and return only the modern
          envelope fields.

        Any unknown or empty ``mode`` resolves to ``legacy`` via
        :func:`resolve_ad_compatibility_mode`, preserving a non-breaking default.
        """

        # Imported lazily to avoid a circular import: ``models`` is imported by
        # the package ``__init__`` before ``apis`` finishes initializing.
        from python_apis.apis.ad_api import (  # pylint: disable=import-outside-toplevel
            resolve_ad_compatibility_mode,
        )

        resolved = resolve_ad_compatibility_mode(per_call_mode=mode)
        payload = self.to_dict()
        if resolved == "strict":
            for legacy_key in ("result", "message"):
                payload.pop(legacy_key, None)
        return payload


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


class ADMembersPage(BaseModel):
    """Typed, paginated view of an AD group's members.

    Returned by ``ADGroupService.get_group_members`` to expose a single page of
    member distinguished names together with paging metadata. The model is the
    response surface for both AD mechanisms used to read large groups: server
    paged search and LDAP ranged attribute retrieval (``member;range=lo-hi``).
    """

    model_config = ConfigDict(extra="forbid")

    members: list[str] = Field(default_factory=list)
    total_count: int = 0
    truncated: bool = False
    page_info: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serializable ``dict`` of this page."""

        return self.model_dump()


__all__: list[str] = [
    # pylint: disable=duplicate-code
    "ADResponse",
    "ADOperationResponse",
    "ADOperationEnvelope",
    "ADEntry",
    "ADSearchResponse",
    "ADMembersPage",
]
