"""Connection-free before/after migration snippets (issue #27).

Each function returns a self-contained string showing the legacy approach and
its modern replacement side by side. The snippets are plain text, require no AD
connection, and are safe to print in a REPL, embed in docs, or surface from
tooling. They complement :mod:`python_apis.discovery` (machine-readable
capability registry) with copy-pasteable code.

Example:
    >>> from python_apis import migration_examples
    >>> print(migration_examples.legacy_get_to_get_v2())  # doctest: +ELLIPSIS
    # Legacy: ambiguous empty-default mapping...
"""


def legacy_get_to_get_v2() -> str:
    """Migrating ``ADConnection.get`` to the typed ``get_v2`` envelope."""

    return (
        "# Legacy: ambiguous empty-default mapping\n"
        "obj = conn.get('(sAMAccountName=jdoe)', ['cn'])\n"
        "if obj.get('cn'):\n"
        "    use(obj)\n"
        "\n"
        "# Modern: explicit found flag via ADGetResult\n"
        "res = conn.get_v2('(sAMAccountName=jdoe)', ['cn'])\n"
        "if res.found:\n"
        "    use(res.item)\n"
        "else:\n"
        "    handle_missing(res.not_found_reason)"
    )


def list_read_to_batch_v2() -> str:
    """Migrating silent-drop list reads to the partial-failure batch result."""

    return (
        "# Legacy: invalid records are logged and silently dropped\n"
        "users = service.get_users_from_ad('(objectClass=user)')\n"
        "\n"
        "# Modern: inspect successes and structured failures\n"
        "result = service.get_users_from_ad_v2('(objectClass=user)')\n"
        "for user in result.returned_items:\n"
        "    use(user)\n"
        "for failure in result.failed_items:\n"
        "    report(failure)"
    )


def raw_multivalue_to_dual_form() -> str:
    """Migrating ad-hoc multi-value parsing to ``normalize_multivalue``."""

    return (
        "# Legacy: manual comma-split, lossy for binary values\n"
        "groups = raw['memberOf'].split(',') if raw.get('memberOf') else []\n"
        "\n"
        "# Modern: dual-form values keep both list and legacy string\n"
        "from python_apis.models import normalize_multivalue\n"
        "mv = normalize_multivalue(raw.get('memberOf'))\n"
        "groups = mv.values             # list form\n"
        "legacy = mv.as_legacy_string()  # verbatim legacy string"
    )


def error_handling_with_taxonomy() -> str:
    """Mapping ad-hoc exception handling to the shared error taxonomy."""

    return (
        "# Legacy: stringly-typed, ad-hoc exception branching\n"
        "try:\n"
        "    conn.add(...)\n"
        "except Exception as exc:\n"
        "    if 'already exists' in str(exc):\n"
        "        ...\n"
        "\n"
        "# Modern: stable error codes from the taxonomy\n"
        "from python_apis.services.error_taxonomy import map_exception_to_error_code\n"
        "try:\n"
        "    conn.add(...)\n"
        "except Exception as exc:\n"
        "    code = map_exception_to_error_code(exc)\n"
        "    handle(code)"
    )


def all_examples() -> dict[str, str]:
    """Return every migration snippet keyed by a stable identifier."""

    return {
        "legacy_get_to_get_v2": legacy_get_to_get_v2(),
        "list_read_to_batch_v2": list_read_to_batch_v2(),
        "raw_multivalue_to_dual_form": raw_multivalue_to_dual_form(),
        "error_handling_with_taxonomy": error_handling_with_taxonomy(),
    }


def print_all() -> None:
    """Print every migration snippet with a labeled header."""

    for name, snippet in all_examples().items():
        print(f"=== {name} ===")
        print(snippet)
        print()


__all__ = [
    "legacy_get_to_get_v2",
    "list_read_to_batch_v2",
    "raw_multivalue_to_dual_form",
    "error_handling_with_taxonomy",
    "all_examples",
    "print_all",
]
