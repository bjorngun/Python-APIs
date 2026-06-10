"""Dual-form representation for Active Directory multivalue attributes (issue #25).

Active Directory multivalue attributes (for example ``proxyAddresses``,
``memberOf``, ``objectClass``) are returned by ldap3 as Python lists. The legacy
schema path flattens these into a single comma-joined string, which loses the
raw source value, element boundaries, and ordering metadata.

This module adds an **additive** dual-form representation, :class:`ADMultiValue`,
that preserves the raw source value, exposes a deterministically normalized
``list[str]``, and carries :class:`ADMultiValueMetadata` describing the source
kind and whether normalization was applied. A legacy delimited-string accessor
(:meth:`ADMultiValue.as_legacy_string`) reproduces the historic comma-joined
string during the transition.

The normalization rules implemented by :func:`normalize_multivalue` are
deterministic and documented in ``docs/migration/ad-multivalue-dual-form.md``.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_DELIMITER = ","

MultiValueSource = Literal["absent", "list", "scalar", "delimited_string"]


class ADMultiValueMetadata(BaseModel):
    """Metadata describing how an :class:`ADMultiValue` was derived."""

    model_config = ConfigDict(extra="forbid")

    source: MultiValueSource = Field(
        description="Kind of the raw source value: absent/list/scalar/delimited_string.",
    )
    normalized: bool = Field(
        description="True when the normalized list was derived/transformed from the raw value.",
    )
    count: int = Field(
        default=0,
        description="Number of elements in the normalized list.",
    )
    delimiter: str = Field(
        default=DEFAULT_DELIMITER,
        description="Delimiter used for delimited-string splitting and the legacy accessor.",
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serializable ``dict`` of this metadata."""

        return self.model_dump()


class ADMultiValue(BaseModel):
    """Dual-form view of an AD multivalue attribute (raw + normalized + metadata).

    Exposes the original ``raw`` source value, a deterministically normalized
    ``values`` list, and ``metadata`` describing the source. Use
    :meth:`as_legacy_string` to reproduce the historic delimiter-joined string.
    """

    model_config = ConfigDict(extra="forbid")

    raw: Any = Field(
        default=None,
        description="Original source value, preserved verbatim (list/str/int/None).",
    )
    values: list[str] = Field(
        default_factory=list,
        description="Deterministically normalized list form.",
    )
    metadata: ADMultiValueMetadata

    @classmethod
    def from_raw(
        cls,
        raw: Any,
        *,
        delimiter: str = DEFAULT_DELIMITER,
    ) -> "ADMultiValue":
        """Build an :class:`ADMultiValue` from a raw AD value.

        Thin wrapper over :func:`normalize_multivalue`.
        """

        return normalize_multivalue(raw, delimiter=delimiter)

    def as_legacy_string(self, delimiter: str | None = None) -> str:
        """Return the historic delimiter-joined string for the normalized values.

        Reproduces the legacy comma-joined representation so existing consumers
        can be served from the dual-form during the transition. When
        ``delimiter`` is ``None`` the delimiter captured in ``metadata`` is used.
        """

        sep = self.metadata.delimiter if delimiter is None else delimiter
        return sep.join(self.values)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-serializable ``dict`` of this dual-form value."""

        return {
            "raw": self.raw,
            "values": list(self.values),
            "metadata": self.metadata.to_dict(),
        }


def normalize_multivalue(
    raw: Any,
    *,
    delimiter: str = DEFAULT_DELIMITER,
) -> ADMultiValue:
    """Build a deterministic dual-form :class:`ADMultiValue` from ``raw``.

    Deterministic normalization rules (same input always yields identical
    output):

    1. ``None`` -> ``values=[]``, ``source="absent"``, ``normalized=False``.
    2. Empty list ``[]`` -> ``values=[]``, ``source="list"``, ``normalized=True``.
    3. ``list`` -> each element ``str(el).strip()``; drop ``None``/empty-after-strip
       elements; preserve order and duplicates; ``source="list"``,
       ``normalized=True``.
    4. Non-``str`` scalar (e.g. ``int``) -> ``values=[str(raw).strip()]`` when
       non-empty; ``source="scalar"``, ``normalized=True``.
    5. ``str`` containing ``delimiter`` -> split on ``delimiter``, ``strip()`` each,
       drop empties, preserve order and duplicates; ``source="delimited_string"``,
       ``normalized=True``.
    6. ``str`` without ``delimiter`` -> ``values=[raw.strip()]`` when non-empty else
       ``[]``; ``source="scalar"``, ``normalized=False``.
    7. ``count = len(values)`` in all cases.

    Args:
        raw: The original AD source value (list/str/int/None).
        delimiter: Delimiter used for delimited-string splitting and recorded in
            metadata for the legacy accessor.

    Returns:
        ADMultiValue: The dual-form representation.
    """

    if raw is None:
        source: MultiValueSource = "absent"
        normalized = False
        values: list[str] = []
    elif isinstance(raw, list):
        source = "list"
        normalized = True
        values = [
            stripped
            for element in raw
            if element is not None and (stripped := str(element).strip())
        ]
    elif isinstance(raw, str):
        if delimiter in raw:
            source = "delimited_string"
            normalized = True
            values = [
                part for piece in raw.split(delimiter) if (part := piece.strip())
            ]
        else:
            source = "scalar"
            normalized = False
            stripped_scalar = raw.strip()
            values = [stripped_scalar] if stripped_scalar else []
    else:
        source = "scalar"
        normalized = True
        stripped_other = str(raw).strip()
        values = [stripped_other] if stripped_other else []

    metadata = ADMultiValueMetadata(
        source=source,
        normalized=normalized,
        count=len(values),
        delimiter=delimiter,
    )
    return ADMultiValue(raw=raw, values=values, metadata=metadata)
