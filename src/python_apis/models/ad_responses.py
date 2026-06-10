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
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import NoInspectionAvailable

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


def _sqlalchemy_to_dict(item: Any) -> dict[str, Any] | None:
    """Return mapped column values for a SQLAlchemy ORM instance, else ``None``.

    Batch read v2 ``returned_items`` hold SQLAlchemy models (``ADUser``,
    ``ADGroup``, ``ADOrganizationalUnit``) that define neither ``to_dict`` nor
    ``model_dump``. This converts such an instance to a plain ``dict`` of its
    mapped column attributes so :meth:`ADBatchReadResult.to_dict` produces a
    serializable payload instead of leaking the raw ORM object.
    """

    try:
        state = sa_inspect(item)
    except NoInspectionAvailable:
        return None
    mapper = getattr(state, "mapper", None)
    if mapper is None:
        return None
    return {attr.key: getattr(item, attr.key) for attr in mapper.column_attrs}


class ADBatchItemFailure(BaseModel):
    """Structured description of a single record that failed a batch read.

    Batch read v2 APIs never silently drop records that fail validation. Each
    failing record is captured as one of these entries so callers can inspect
    exactly which record failed and why.
    """

    model_config = ConfigDict(extra="forbid")

    identity: str | None = Field(
        default=None,
        description="Best-effort identity of the failing record (dn / account id).",
    )
    failure_classification: str = Field(
        default="validation",
        description="Coarse failure category, e.g. 'validation'.",
    )
    error_code: str = Field(
        description="Canonical error taxonomy code, e.g. 'AD_VALIDATION_ERROR'.",
    )
    raw_validation_details: Any = Field(
        default=None,
        description="Underlying validation/error details for diagnostics.",
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serializable ``dict`` of this failure."""

        return self.model_dump()


class ADBatchReadResult(BaseModel):
    """Partial-failure-aware envelope returned by batch read v2 APIs.

    Unlike the legacy ``list``-returning read methods, which discard records
    that fail schema validation, this envelope surfaces both successfully built
    records (``returned_items``) and structured failures (``failed_items``) so
    no record is silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    returned_items: list[Any] = Field(default_factory=list)
    failed_items: list[ADBatchItemFailure] = Field(default_factory=list)
    totals: dict[str, int] = Field(default_factory=dict)
    continuation_state: Any = Field(
        default=None,
        description="Opaque continuation token; reserved for future paged reads.",
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serializable ``dict`` of this result.

        ``returned_items`` are converted with ``to_dict`` when available so the
        whole envelope round-trips to JSON-serializable primitives.
        """

        def _item_to_dict(item: Any) -> Any:
            to_dict = getattr(item, "to_dict", None)
            if callable(to_dict):
                return to_dict()
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                return model_dump()
            mapped = _sqlalchemy_to_dict(item)
            if mapped is not None:
                return mapped
            return item

        return {
            "returned_items": [_item_to_dict(item) for item in self.returned_items],
            "failed_items": [failure.to_dict() for failure in self.failed_items],
            "totals": dict(self.totals),
            "continuation_state": self.continuation_state,
        }


# Mirrors ``python_apis.services.error_taxonomy.AD_NOT_FOUND``. Duplicated here as a
# string literal because the models layer cannot import the services constant without
# a circular import (``services/__init__`` imports the AD services, which import this
# models layer).
_AD_NOT_FOUND_CODE = "AD_NOT_FOUND"

ADGetNotFoundReason = Literal["no_match"]


class ADGetResult(BaseModel):
    """Typed found/not-found envelope returned by single-object ``get_v2`` reads.

    The legacy ``ADConnection.get`` returns the first matched object as a ``dict``
    or an empty ``defaultdict`` when nothing matches, which is indistinguishable
    from a real object whose attributes are all empty. This envelope instead
    carries an explicit ``found`` flag plus a deterministic ``not_found_reason`` so
    callers can reliably tell "absent" from "present but empty".
    """

    model_config = ConfigDict(extra="forbid")

    found: bool = Field(
        description="True when an object matched and is present in ``item``.",
    )
    item: Any = Field(
        default=None,
        description="The matched AD object (first match when several matched); None when absent.",
    )
    not_found_reason: ADGetNotFoundReason | None = Field(
        default=None,
        description="Deterministic reason the object was absent, e.g. 'no_match'. None when found.",
    )
    error_code: str | None = Field(
        default=None,
        description="Canonical error taxonomy code for the absence, e.g. 'AD_NOT_FOUND'. None when found.",
    )

    @classmethod
    def found_item(cls, item: Any) -> "ADGetResult":
        """Build a found result wrapping ``item``."""

        return cls(found=True, item=item)

    @classmethod
    def not_found(
        cls, reason: ADGetNotFoundReason = "no_match"
    ) -> "ADGetResult":
        """Build a not-found result with a deterministic ``reason`` and error code."""

        return cls(
            found=False,
            not_found_reason=reason,
            error_code=_AD_NOT_FOUND_CODE,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serializable ``dict`` of this result."""

        item = self.item
        to_dict = getattr(item, "to_dict", None)
        if callable(to_dict):
            item = to_dict()
        else:
            mapped = _sqlalchemy_to_dict(item)
            if mapped is not None:
                item = mapped

        return {
            "found": self.found,
            "item": item,
            "not_found_reason": self.not_found_reason,
            "error_code": self.error_code,
        }


__all__: list[str] = [
    # pylint: disable=duplicate-code
    "ADResponse",
    "ADOperationResponse",
    "ADOperationEnvelope",
    "ADEntry",
    "ADSearchResponse",
    "ADMembersPage",
    "ADBatchItemFailure",
    "ADBatchReadResult",
    "ADGetResult",
]
