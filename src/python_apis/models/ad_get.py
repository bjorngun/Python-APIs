"""Typed found/not-found envelope for single-object AD reads (issue #26).

The legacy single-object read ``python_apis.apis.ad_api.ADConnection.get`` returns
the first matched object as a ``dict`` or an empty ``defaultdict`` when nothing
matches. That empty default is indistinguishable from a real object whose
attributes are all empty, so callers cannot reliably tell "absent" from "present
but empty".

This module adds an **additive** typed envelope, :class:`ADGetResult`, returned by
the ``get_v2`` counterpart. It carries an explicit ``found`` flag plus a
deterministic ``not_found_reason`` so absence is unambiguous. The legacy ``get``
behavior is unchanged.

This module intentionally depends only on ``pydantic`` so the API layer can import
it without a circular import (``models.ad_responses`` lazily imports the API layer,
so ``ADConnection`` cannot import from that module).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Mirrors ``python_apis.services.error_taxonomy.AD_NOT_FOUND``. Duplicated here as a
# plain string because the services constant cannot be imported without a circular
# import (``services/__init__`` imports the AD services, which import the API layer).
AD_NOT_FOUND_CODE = "AD_NOT_FOUND"

ADGetNotFoundReason = Literal["no_match"]


class ADGetResult(BaseModel):
    """Typed found/not-found envelope returned by single-object ``get_v2`` reads.

    Carries an explicit ``found`` flag plus a deterministic ``not_found_reason`` so
    callers can reliably distinguish "absent" from "present but empty", unlike the
    legacy ``get`` which returns an empty mapping for both.
    """

    model_config = ConfigDict(extra="forbid")

    found: bool = Field(
        description="True when an object matched and is present in ``item``.",
    )
    item: dict[str, Any] | None = Field(
        default=None,
        description="Matched AD object mapping (first match when several); None when absent.",
    )
    not_found_reason: ADGetNotFoundReason | None = Field(
        default=None,
        description="Deterministic absence reason, e.g. 'no_match'. None when found.",
    )
    error_code: str | None = Field(
        default=None,
        description="Canonical error taxonomy code for the absence, e.g. 'AD_NOT_FOUND'.",
    )

    @model_validator(mode="after")
    def _check_found_invariants(self) -> "ADGetResult":
        """Reject internally inconsistent envelopes.

        A found result must carry an ``item`` and no absence metadata; a
        not-found result must omit ``item`` and carry a ``not_found_reason``.
        Validating at construction keeps this public contract type unambiguous.
        """

        if self.found:
            if self.item is None:
                raise ValueError("found result requires a non-None item")
            if self.not_found_reason is not None or self.error_code is not None:
                raise ValueError("found result must not carry not-found metadata")
        else:
            if self.item is not None:
                raise ValueError("not-found result must not carry an item")
            if self.not_found_reason is None:
                raise ValueError("not-found result requires a not_found_reason")
        return self

    @classmethod
    def found_item(cls, item: dict[str, Any]) -> "ADGetResult":
        """Build a found result wrapping ``item``."""

        return cls(found=True, item=item)

    @classmethod
    def not_found(cls, reason: ADGetNotFoundReason = "no_match") -> "ADGetResult":
        """Build a not-found result with a deterministic ``reason`` and error code."""

        return cls(found=False, not_found_reason=reason, error_code=AD_NOT_FOUND_CODE)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain ``dict`` view of this result.

        ``item`` is included as-is: for ``get_v2`` it is the raw AD object mapping
        (or ``None`` when absent), which is already a plain ``dict``.
        """

        return {
            "found": self.found,
            "item": self.item,
            "not_found_reason": self.not_found_reason,
            "error_code": self.error_code,
        }


__all__ = [
    "ADGetResult",
    "ADGetNotFoundReason",
    "AD_NOT_FOUND_CODE",
]
