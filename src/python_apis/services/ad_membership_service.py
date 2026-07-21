"""Strict AD-only group lookup and membership reads."""

from python_apis.apis import ADConnection, escape_filter_value
from python_apis.apis.ad_errors import ADMalformedQueryError, ADMalformedResultError
from python_apis.models import ADGetResult


class ADMembershipService:  # pylint: disable=too-few-public-methods
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


__all__ = ["ADMembershipService"]
