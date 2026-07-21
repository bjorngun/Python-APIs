"""Perform a resilient LDAP read using only the public package API.

Required environment variables:

- ``LDAP_SERVER_LIST``: whitespace-separated controller names.
- ``SEARCH_BASE``: default LDAP search base.

The example prints only aggregate count and masked retry telemetry, not records or raw controllers.
"""

# pylint: disable=duplicate-code

import os

from python_apis.apis import (
    ADBindError,
    ADConnection,
    ADMissingServersError,
    AD_RECOVERABLE_READ_EXCEPTIONS,
)


def build_connection() -> ADConnection:
    """Build an AD connection from environment configuration."""

    servers = os.getenv("LDAP_SERVER_LIST", "").split()
    search_base = os.getenv("SEARCH_BASE", "")
    return ADConnection(
        servers,
        search_base,
        receive_timeout=30,
        connect_timeout=5,
        page_size=500,
        read_retry_count=1,
        read_retry_backoff_seconds=0.5,
        write_retry_count=0,
    )


def report_read_failure(connection: ADConnection) -> None:
    """Print sanitized aggregate diagnostics for an exhausted read."""

    telemetry = connection.last_retry_telemetry
    if telemetry is None:
        print("LDAP read failed: retry telemetry unavailable")
        return
    print(
        "LDAP read failed: "
        f"attempts={telemetry.attempt_count} "
        f"retries={telemetry.retry_count} "
        f"failed_controller={telemetry.failed_server} "
        f"selected_controller={telemetry.selected_server}"
    )


def main() -> None:
    """Read users and print aggregate retry diagnostics."""

    try:
        connection = build_connection()
    except ADMissingServersError:
        print("No LDAP controllers are configured.")
        return
    except ADBindError as error:
        print(
            "LDAP bind failed: "
            f"result_code={error.result_code!r} controller={error.controller}"
        )
        return

    try:
        users = connection.search(
            "(&(objectClass=user)(objectCategory=person))",
            ["distinguishedName"],
        )
    except AD_RECOVERABLE_READ_EXCEPTIONS:
        report_read_failure(connection)
        return
    print(f"Completed LDAP read: returned_count={len(users)}")

    telemetry = connection.last_retry_telemetry
    if telemetry is not None:
        print(
            "Retry telemetry: "
            f"attempts={telemetry.attempt_count} "
            f"retries={telemetry.retry_count} "
            f"recovered={telemetry.recovered} "
            f"failed_controller={telemetry.failed_server} "
            f"selected_controller={telemetry.selected_server} "
            f"elapsed_seconds={telemetry.elapsed_seconds:.3f}"
        )


if __name__ == "__main__":
    main()
