"""Resolve generic inherited OU values with one tree per synchronization run.

Required environment variables:

- ``LDAP_SERVER_LIST``: whitespace-separated controller names.
- ``SEARCH_BASE``: default LDAP search base.

The example uses neutral object fields/defaults and prints only aggregate counts.
"""

# pylint: disable=duplicate-code

from dataclasses import dataclass
import os

from python_apis.apis import (
    ADBindError,
    ADConnection,
    ADMissingServersError,
    AD_RECOVERABLE_READ_EXCEPTIONS,
)
from python_apis.services import (
    ADOrganizationalUnitService,
    ADOrganizationalUnitTreeError,
    OUAttributeRule,
    OUInheritanceCycleError,
)

class DirectoryObjectReadError(ValueError):
    """Raised when a directory result has no safely derived OU DN."""

    def __init__(self, entry_index: int) -> None:
        self.entry_index = entry_index
        super().__init__(f"Directory entry {entry_index} has no organizational unit")


@dataclass
class DirectoryObject:
    """Consumer-owned object used only for this neutral example."""

    organizational_unit_dn: str
    department_code: object | None = None
    office_phone: object | None = None
    office_address: object | None = None
    postal_code: object | None = None


def remove_hyphens(value: object) -> str:
    """Return text without hyphens for a caller-owned normalization rule."""

    return str(value).replace("-", "")


def is_numeric_text(value: object) -> bool:
    """Return whether a normalized candidate contains only digits."""

    return str(value).isdigit()


def build_rules() -> dict[str, OUAttributeRule]:
    """Build consumer-neutral example rules."""

    return {
        "department_code": OUAttributeRule(
            source="description",
            normalize=remove_hyphens,
            accept=is_numeric_text,
            default=None,
        ),
        "office_phone": OUAttributeRule(
            source="telephoneNumber",
            default=None,
        ),
        "office_address": OUAttributeRule(
            source="street",
            aliases=("streetAddress",),
            default=None,
        ),
        "postal_code": OUAttributeRule(
            source="postalCode",
            default=None,
        ),
    }


def build_connection() -> ADConnection:
    """Build the shared connection from environment configuration."""

    return ADConnection(
        os.getenv("LDAP_SERVER_LIST", "").split(),
        os.getenv("SEARCH_BASE", ""),
        receive_timeout=30,
        page_size=500,
        read_retry_count=1,
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


def read_objects(connection: ADConnection) -> list[DirectoryObject]:
    """Read objects and require an immediate OU DN for every result."""

    entries = connection.search(
        "(&(objectClass=user)(objectCategory=person))",
        ["distinguishedName"],
    )
    objects: list[DirectoryObject] = []
    for entry_index, entry in enumerate(entries):
        organizational_unit_dn = entry.get("ou")
        if not isinstance(organizational_unit_dn, str):
            raise DirectoryObjectReadError(entry_index)
        objects.append(DirectoryObject(organizational_unit_dn=organizational_unit_dn))
    return objects


def get_object_ou_dn(item: object) -> str | None:
    """Return the OU DN from this example's consumer-owned object type."""

    if isinstance(item, DirectoryObject):
        return item.organizational_unit_dn
    return None


def enrich_objects(
    objects: list[DirectoryObject],
    connection: ADConnection,
) -> None:
    """Resolve one shared OU tree and explicitly apply returned values."""

    rules = build_rules()
    ou_service = ADOrganizationalUnitService.for_active_directory(connection)
    attributes = [
        attribute
        for rule in rules.values()
        for attribute in (rule.source, *rule.aliases)
    ]
    ou_tree = ou_service.get_ou_tree(attributes=attributes)
    resolved_rows = ou_service.resolve_inherited_attributes_for_objects(
        objects,
        rules,
        get_ou_dn=get_object_ou_dn,
        ou_tree=ou_tree,
    )
    for item, values in zip(objects, resolved_rows):
        for target, value in values.items():
            setattr(item, target, value)


def main() -> None:
    """Read and enrich objects while reporting only aggregate status."""

    try:
        connection = build_connection()
        objects = read_objects(connection)
        enrich_objects(objects, connection)
    except ADMissingServersError:
        print("No LDAP controllers are configured.")
        return
    except ADBindError as error:
        print(
            "LDAP bind failed: "
            f"result_code={error.result_code!r} controller={error.controller}"
        )
        return
    except AD_RECOVERABLE_READ_EXCEPTIONS:
        report_read_failure(connection)
        return
    except DirectoryObjectReadError as error:
        print(f"Directory object read failed: entry_index={error.entry_index}")
        return
    except (ADOrganizationalUnitTreeError, OUInheritanceCycleError) as error:
        print(f"OU enrichment failed: {type(error).__name__}")
        return

    print(f"Completed OU enrichment: object_count={len(objects)}")


if __name__ == "__main__":
    main()
