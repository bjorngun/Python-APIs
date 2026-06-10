"""Canonical usage example for the AD multivalue dual-form representation (issue #25).

Demonstrates :func:`normalize_multivalue` and :class:`ADMultiValue`, which preserve
the raw AD source value, expose a deterministically normalized ``list[str]``, and
carry metadata describing the source kind and normalization status. The legacy
delimiter-joined string remains available via ``as_legacy_string()`` during the
transition.

This example imports only the public package surface and needs no AD connection.
Run with: ``python examples/multivalue_dual_form.py``.
"""

from python_apis.models import ADMultiValue, normalize_multivalue


def print_dual_form(label: str, value: ADMultiValue) -> None:
    """Print the raw, normalized, and metadata views of a dual-form value."""

    print(f"{label}:")
    print(f"  raw       = {value.raw!r}")
    print(f"  values    = {value.values}")
    print(f"  metadata  = {value.metadata.to_dict()}")
    print(f"  legacy    = {value.as_legacy_string()!r}")


def main() -> None:
    """Show dual-form handling across the documented source kinds."""

    # True multivalue attribute (list), as ldap3 returns proxyAddresses.
    print_dual_form(
        "list source",
        normalize_multivalue(["SMTP:a@x", "smtp:b@x"]),
    )

    # Legacy delimited string (already flattened upstream).
    print_dual_form(
        "delimited string source",
        normalize_multivalue("a@x, b@x"),
    )

    # Single scalar value.
    print_dual_form(
        "scalar source",
        ADMultiValue.from_raw("single-value"),
    )

    # Absent value.
    print_dual_form(
        "absent source",
        normalize_multivalue(None),
    )


if __name__ == "__main__":
    main()
