"""Canonical usage examples for the AD batch read v2 APIs (issue #24).

Demonstrates the partial-failure-aware batch read methods added to the AD
services:

* :meth:`ADUserService.get_users_from_ad_v2`
* :meth:`ADGroupService.get_groups_from_ad_v2`
* :meth:`ADOrganizationalUnitService.get_ous_from_ad_v2`

Unlike the legacy ``list``-returning read methods, which silently drop records
that fail schema validation, these v2 methods return an ``ADBatchReadResult``
envelope exposing both successfully built records (``returned_items``) and
structured per-record failures (``failed_items``).

These examples import only the public package surface. They assume the standard
in-domain AD connection environment variables (``LDAP_SERVER_LIST``,
``SEARCH_BASE``, and the AD DB settings) are configured; see the project README.
Run with: ``python examples/batch_read_v2.py``.
"""

from python_apis.models import ADBatchReadResult
from python_apis.services import ADUserService


def print_batch_result(result: ADBatchReadResult) -> None:
    """Print returned items and any structured failures from a batch read."""

    print(f"totals: {result.totals}")

    print(f"returned {len(result.returned_items)} item(s):")
    for item in result.returned_items:
        # Returned items are fully built models (e.g. ADUser/ADGroup/ADOrgUnit).
        identity = getattr(item, "distinguishedName", None)
        print(f"  - {identity}")

    print(f"failed {len(result.failed_items)} item(s):")
    for failure in result.failed_items:
        # No record is silently dropped: each failure is fully described.
        print(
            f"  - identity={failure.identity} "
            f"code={failure.error_code} "
            f"class={failure.failure_classification}"
        )
        # failure.raw_validation_details holds the underlying validation errors.


def read_users_v2(service: ADUserService) -> None:
    """Read users as a partial-failure-aware batch envelope."""

    result = service.get_users_from_ad_v2("(objectClass=user)")
    print_batch_result(result)

    # The envelope is JSON-serializable for logging/transport.
    _ = result.to_dict()


def main() -> None:
    """Entry point: construct the service and run the batch read example."""

    service = ADUserService()
    read_users_v2(service)


if __name__ == "__main__":
    main()
