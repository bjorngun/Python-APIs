"""Strict AD-only group lookup and membership reads."""

from python_apis.apis import ADConnection, escape_filter_value
from python_apis.apis.ad_errors import ADMalformedQueryError, ADMalformedResultError
from python_apis.models import ADGetResult, ADGroupMembersResult

LDAP_MATCHING_RULE_BIT_AND = "1.2.840.113556.1.4.803"
LDAP_MATCHING_RULE_IN_CHAIN = "1.2.840.113556.1.4.1941"


class ADMembershipService:
    """Provide safe membership queries without SQL or snapshot persistence."""

    def __init__(self, ad_connection: ADConnection) -> None:
        self.ad_connection = ad_connection

    def resolve_group_dn(self, group_id: str) -> ADGetResult:
        """Resolve one current group DN from its stable ``sAMAccountName``."""

        if not isinstance(group_id, str) or not group_id.strip():
            raise ADMalformedQueryError()
        escaped_group_id = escape_filter_value(group_id)
        search_filter = (
            "(&(objectCategory=group)(objectClass=group)"
            f"(sAMAccountName={escaped_group_id}))"
        )
        groups = self.ad_connection.search_strict(
            search_filter,
            ["distinguishedName"],
        )
        if not groups:
            return ADGetResult.not_found()
        if len(groups) != 1:
            raise ADMalformedResultError()
        group_dn = groups[0].get("distinguishedName")
        if not isinstance(group_dn, str) or not group_dn.strip():
            raise ADMalformedResultError()
        return ADGetResult.found_item({"distinguishedName": group_dn})

    def get_transitive_enabled_group_members(
        self,
        group_id: str,
    ) -> ADGroupMembersResult:
        """Return all enabled user accounts transitively in a stable group ID."""

        group = self.resolve_group_dn(group_id)
        if not group.found:
            return ADGroupMembersResult.not_found()
        group_item = group.item
        if not isinstance(group_item, dict):
            raise ADMalformedResultError()
        group_dn = group_item.get("distinguishedName")
        if not isinstance(group_dn, str) or not group_dn.strip():
            raise ADMalformedResultError()

        escaped_group_dn = escape_filter_value(group_dn)
        search_filter = (
            "(&(objectCategory=person)(objectClass=user)"
            f"(!(userAccountControl:{LDAP_MATCHING_RULE_BIT_AND}:=2))"
            f"(memberOf:{LDAP_MATCHING_RULE_IN_CHAIN}:={escaped_group_dn}))"
        )
        users = self.ad_connection.search_strict(
            search_filter,
            ["sAMAccountName"],
        )
        members: set[str] = set()
        for user in users:
            account_name = user.get("sAMAccountName")
            if not isinstance(account_name, str) or not account_name.strip():
                raise ADMalformedResultError()
            members.add(account_name.casefold())
        return ADGroupMembersResult.found(members)


__all__ = [
    "ADMembershipService",
    "LDAP_MATCHING_RULE_BIT_AND",
    "LDAP_MATCHING_RULE_IN_CHAIN",
]
