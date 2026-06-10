"""Canonical usage examples for the AD membership APIs v2 (issue #23).

Demonstrates the two read APIs added to ``ADGroupService``:

* :meth:`ADGroupService.get_user_transitive_groups` - resolve every group a user
  belongs to, including nested (indirect) memberships, deterministically.
* :meth:`ADGroupService.get_group_members` - read a group's members at scale
  using LDAP ranged retrieval, returning a paged ``ADMembersPage`` envelope with
  ``total_count``, ``page_info`` and ``truncated``.

These examples import only the public package surface. They assume the standard
in-domain AD connection environment variables (``LDAP_SERVER_LIST``,
``SEARCH_BASE``, and the AD DB settings) are configured; see the project README.
Run with: ``python examples/membership_apis.py``.
"""

from python_apis.models import ADMembersPage
from python_apis.services import ADGroupService


def print_transitive_groups(service: ADGroupService, user_dn: str) -> None:
    """Print all (direct and nested) groups the user belongs to."""

    groups = service.get_user_transitive_groups(user_dn)
    print(f"{user_dn} is a (transitive) member of {len(groups)} groups:")
    for group in groups:
        print(f"  - {group.distinguishedName}")


def iterate_group_members(
    service: ADGroupService,
    group_dn: str,
    page_size: int = 500,
) -> list[str]:
    """Page through every member of a group and return the collected DNs.

    Iterates by following ``page_info['next_offset']`` until ``has_next_page``
    is ``False``, which is the canonical paging loop for large groups.
    """

    all_members: list[str] = []
    offset = 0
    while True:
        page: ADMembersPage = service.get_group_members(
            group_dn,
            page_size=page_size,
            offset=offset,
        )
        all_members.extend(page.members)
        print(
            f"Fetched {len(page.members)} members "
            f"(offset={page.page_info['offset']}, total={page.total_count})"
        )
        if not page.page_info["has_next_page"]:
            break
        offset = page.page_info["next_offset"]

    return all_members


def main() -> None:
    """Run the membership API examples against the configured AD environment."""

    service = ADGroupService()

    # 1) Resolve a user's full (nested) group membership.
    print_transitive_groups(service, "CN=John Doe,OU=Users,DC=example,DC=com")

    # 2) Page through a (potentially very large) group's members.
    members = iterate_group_members(
        service,
        "CN=All Staff,OU=Groups,DC=example,DC=com",
        page_size=500,
    )
    print(f"Collected {len(members)} total members.")


if __name__ == "__main__":
    main()
