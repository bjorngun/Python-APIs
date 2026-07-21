"""Resolve generic inherited OU values with one tree per synchronization run.

Required environment variables:

- ``LDAP_SERVER_LIST``: whitespace-separated controller names.
- ``SEARCH_BASE``: default LDAP search base.

The example uses neutral object fields/defaults and prints only aggregate counts.
"""

from dataclasses import dataclass
import os

from python_apis.apis import ADBindError, ADConnection, ADMissingServersError
from python_apis.services import (
    ADOrganizationalUnitService,
    ADOrganizationalUnitTreeError,
    OUAttributeRule,
    OUInheritanceCycleError,
)


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


def read_objects(connection: ADConnection) -> list[DirectoryObject]:
    """Read objects and retain only their immediate OU DNs."""

    entries = connection.search(
        "(&(objectClass=user)(objectCategory=person))",
        ["distinguishedName"],
    )
    return [
        DirectoryObject(organizational_unit_dn=entry["ou"])
        for entry in entries
        if isinstance(entry.get("ou"), str)
    ]


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
        get_ou_dn=lambda item: item.organizational_unit_dn,
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
    except (ADOrganizationalUnitTreeError, OUInheritanceCycleError) as error:
        print(f"OU enrichment failed: {type(error).__name__}")
        return

    print(f"Completed OU enrichment: object_count={len(objects)}")


if __name__ == "__main__":
    main()
