"""Canonical usage example and migration helpers for the AD ``get_v2`` API (issue #26).

The legacy single-object read ``ADConnection.get`` returns the first matched
object as a ``dict`` or an empty ``collections.defaultdict`` when nothing matches.
That empty default is indistinguishable from a real object whose attributes are
all empty, so callers cannot reliably tell "absent" from "present but empty".

``ADConnection.get_v2`` is the additive, typed counterpart: it returns an
``ADGetResult`` envelope with an explicit ``found`` flag and a deterministic
``not_found_reason``. The legacy ``get`` behavior is unchanged.

The ``demo_envelope`` function below runs with no AD connection. The connection
based functions assume the standard in-domain AD environment variables
(``LDAP_SERVER_LIST``, ``SEARCH_BASE``) are configured; see the project README.
Run with: ``python examples/get_v2.py``.
"""

from python_apis.apis import ADConnection
from python_apis.models import ADGetResult


def demo_envelope() -> None:
    """Show the dual found/not-found shape without needing an AD connection."""

    found = ADGetResult.found_item({"sAMAccountName": "jdoe", "cn": "John Doe"})
    print("found:")
    print(f"  found             = {found.found}")
    print(f"  item              = {found.item}")
    print(f"  not_found_reason  = {found.not_found_reason}")
    print(f"  to_dict()         = {found.to_dict()}")

    absent = ADGetResult.not_found()
    print("absent:")
    print(f"  found             = {absent.found}")
    print(f"  item              = {absent.item}")
    print(f"  not_found_reason  = {absent.not_found_reason}")
    print(f"  error_code        = {absent.error_code}")
    print(f"  to_dict()         = {absent.to_dict()}")


def get_v2_usage(conn: ADConnection, search_filter: str) -> None:
    """Branch on the explicit ``found`` flag instead of probing dict keys."""

    result = conn.get_v2(search_filter, ["cn", "sAMAccountName"])
    if result.found:
        print(f"found object: {result.item}")
    else:
        # Deterministic absence: no_match -> AD_NOT_FOUND.
        print(f"not found ({result.not_found_reason}, {result.error_code})")


def migrate_get_callsite(conn: ADConnection, search_filter: str) -> dict | None:
    """Migration helper: replace ``conn.get(...)`` with an explicit Optional.

    Legacy callers wrote::

        obj = conn.get(search_filter, attrs)
        if obj.get("sAMAccountName"):   # ambiguous: empty default vs empty attr
            ...

    With ``get_v2`` the presence check is unambiguous. This helper returns the
    matched mapping or ``None``, so existing ``Optional[dict]`` consumers can adopt
    the typed API with a one-line change.
    """

    result = conn.get_v2(search_filter, ["cn", "sAMAccountName"])
    return result.item if result.found else None


def main() -> None:
    """Run the connection-free envelope demo."""

    demo_envelope()


if __name__ == "__main__":
    main()
