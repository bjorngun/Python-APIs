"""Shared helper for partial-failure-aware AD batch read v2 APIs.

This module centralizes the validate/build/classify loop used by the AD service
``get_*_from_ad_v2`` methods. Unlike the legacy ``list``-returning read methods,
which discard records that fail schema validation, the helper here captures each
failing record as a structured :class:`ADBatchItemFailure` so no record is
silently dropped.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

from python_apis.models import ADBatchItemFailure, ADBatchReadResult
from python_apis.services.error_taxonomy import map_exception_to_error_code

# Default ordered identity fields, most specific first.
DEFAULT_IDENTITY_FIELDS: tuple[str, ...] = (
    "distinguishedName",
    "sAMAccountName",
    "objectGUID",
    "objectSid",
)


def resolve_identity(
    record: Mapping[str, Any],
    identity_fields: Sequence[str] = DEFAULT_IDENTITY_FIELDS,
) -> str | None:
    """Return a best-effort identity string for ``record``.

    The first non-empty value among ``identity_fields`` (in order) is returned.
    List/tuple values are reduced to their first element. Returns ``None`` when
    no identity field carries a usable value.
    """

    for field in identity_fields:
        value = record.get(field)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value not in (None, ""):
            return str(value)
    return None


def build_batch_read_result(
    records: Sequence[Mapping[str, Any]],
    *,
    schema: type[BaseModel],
    model_factory: Callable[..., Any],
    identity_fields: Sequence[str] = DEFAULT_IDENTITY_FIELDS,
    preprocess: Callable[[Any], Mapping[str, Any]] | None = None,
) -> ADBatchReadResult:
    """Validate and build ``records``, surfacing partial failures.

    Args:
        records: Raw AD search records (mappings of attribute name to value).
        schema: Pydantic schema used to validate/normalize each record.
        model_factory: Callable invoked with the validated data to build the
            returned item (typically the model class).
        identity_fields: Ordered attribute names used to resolve a failing
            record's identity.
        preprocess: Optional callable applied to each record (inside the
            per-record error boundary) before validation. May mutate and/or
            return the record; the returned value is validated.

    Returns:
        ADBatchReadResult: Envelope with ``returned_items`` for successfully
        built records and ``failed_items`` for records that failed. ``totals``
        carries ``requested``/``returned``/``failed`` counts and
        ``continuation_state`` is ``None`` (reserved for future paged reads).

    The per-record error boundary is total: schema ``ValidationError`` is
    classified as ``"validation"``, while any other exception raised by
    ``preprocess`` or ``model_factory`` (for example a missing attribute during
    annotation) is classified as ``"processing"``. Either way the failing record
    is captured in ``failed_items`` rather than aborting the whole batch.
    """

    returned_items: list[Any] = []
    failed_items: list[ADBatchItemFailure] = []

    for record in records:
        try:
            data = preprocess(record) if preprocess is not None else record
            if data is None:
                data = record
            validated_data = schema(**data).model_dump()
            returned_items.append(model_factory(**validated_data))
        except ValidationError as exc:
            failed_items.append(
                ADBatchItemFailure(
                    identity=resolve_identity(record, identity_fields),
                    failure_classification="validation",
                    error_code=map_exception_to_error_code(exc),
                    raw_validation_details=exc.errors(),
                )
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Preserve the partial-failure contract: a non-validation error on a
            # single record (e.g. a missing attribute during preprocessing) must
            # not abort the batch or drop already-built records.
            failed_items.append(
                ADBatchItemFailure(
                    identity=resolve_identity(record, identity_fields),
                    failure_classification="processing",
                    error_code=map_exception_to_error_code(exc),
                    raw_validation_details=str(exc),
                )
            )

    return ADBatchReadResult(
        returned_items=returned_items,
        failed_items=failed_items,
        totals={
            "requested": len(records),
            "returned": len(returned_items),
            "failed": len(failed_items),
        },
        continuation_state=None,
    )
