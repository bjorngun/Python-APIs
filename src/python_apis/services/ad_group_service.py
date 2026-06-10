"""
Module providing the ADGroupService class for interacting with Active Directory groups.
"""

# pylint: disable=duplicate-code

from logging import getLogger
import os
from typing import Any

from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from pydantic import ValidationError

from dev_tools import timing_decorator
from python_apis.apis import ADConnection, SQLConnection
from python_apis.models import ADGroup, ADUser, base
from python_apis.schemas import ADGroupSchema
from python_apis.services.compatibility_mode import (
    finalize_ad_write_response,
    resolve_service_compatibility_mode,
)

class ADGroupService:
    """Service class for interacting with Active Directory groups.

        Compatibility mode contract:
        - Supported modes are ``legacy``, ``mixed``, and ``strict``.
        - Effective mode precedence is per-call override, then service default,
            then `PYTHON_APIS_AD_COMPAT_MODE`, then ``legacy`` fallback.
        - Invalid or empty mode values must resolve to ``legacy`` deterministically.
    """

    def __init__(
        self,
        ad_connection: ADConnection = None,
        sql_connection: SQLConnection = None,
        ldap_logging: bool = False,
        compatibility_mode: str | None = None,
    ):
        """Initialize the ADGroupService with an ADConnection and a db connection.

        Args:
            ad_connection (ADConnection, optional): An existing ADConnection instance.
                If None, a new one will be created.
            sql_connection (SQLConnection, optional): An existing SQLConnection instance.
                If None, a new one will be created.
            ldap_logging (bool, optional): Whether to enable LDAP logging. Defaults to False.
            compatibility_mode (str | None, optional): Default compatibility mode for the
                service instance. Resolved with deterministic precedence against environment
                defaults and fallback behavior.
        """
        self.logger = getLogger(__name__)
        self.compatibility_mode = resolve_service_compatibility_mode(
            service_mode=compatibility_mode
        )

        if sql_connection is None:
            sql_connection = self._get_sql_connection()
        self.sql_connection = sql_connection

        if ad_connection is None:
            ad_connection = self._get_ad_connection(ldap_logging)
        self.ad_connection = ad_connection

    def _resolve_effective_mode(self, compatibility_mode: str | None = None) -> str:
        """Resolve effective compatibility mode for a service operation."""
        return resolve_service_compatibility_mode(
            per_call_mode=compatibility_mode,
            service_mode=self.compatibility_mode,
        )

    def get_compatibility_mode(self, compatibility_mode: str | None = None) -> dict[str, str]:
        """Return service default and effective compatibility mode for this context."""
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        return {
            'service_default_mode': self.compatibility_mode,
            'effective_mode': effective_mode,
        }

    def _get_sql_connection(self) -> SQLConnection:
        """Create and return a SQLConnection instance based on environment variables.

        Returns:
            SQLConnection: A new SQLConnection instance configured from environment variables.
        """
        return SQLConnection(
            server=os.getenv('AD_DB_SERVER', os.getenv('DEFAULT_DB_SERVER')),
            database=os.getenv('AD_DB_NAME', os.getenv('DEFAULT_DB_NAME')),
            driver=os.getenv('AD_SQL_DRIVER', os.getenv('DEFAULT_SQL_DRIVER')),
        )

    def create_table(self):
        """Create the ADGroup table in the database if it does not exist."""
        base.Base.metadata.create_all(
            self.sql_connection.engine, tables=[ADGroup.__table__], checkfirst=True)

    @timing_decorator
    def _get_ad_connection(self, ldap_logging: bool) -> ADConnection:
        """Create and return an ADConnection instance.

        Returns:
            ADConnection: A new ADConnection instance based on environment variables.
        """
        ad_servers = os.getenv("LDAP_SERVER_LIST").split()
        search_base = os.getenv("SEARCH_BASE")
        ad_connection = ADConnection(ad_servers, search_base, ldap_logging)
        return ad_connection

    @timing_decorator
    def get_groups_from_db(self) -> list[ADGroup]:
        """Retrieve groups from the database.

        Returns:
            list[ADGroup]: A list of all ADGroup instances in the database.
        """
        ad_groups = self.sql_connection.session.query(ADGroup).all()
        return ad_groups

    def set_group_type_name(self, ad_group: dict[str, Any]) -> None:
        '''Get name of type of group for the integer representing the group in AD'''
        ad_group['groupType_name'] = ADGroup.get_group_type_name(ad_group['groupType'])

    @timing_decorator
    def update_group_db(self):
        """
        Update the group database with the latest groups from Active Directory.

        This method performs the following actions:

        1. Retrieves all group entries from Active Directory by calling `get_groups_from_ad()`.
        2. Updates existing records or adds new ones to the local database.
        3. Commits the transaction to save the changes to the database.

        If an exception occurs during the database operations, the method will:

        - Roll back the current transaction to prevent partial commits.
        - Log an error message with details about the exception.
        - Re-raise the original exception to be handled by the calling code.

        Note:
            - This method is decorated with `@timing_decorator`, which measures and logs the
            execution time.
            - Ensure that the database connection is properly configured and active before
            calling this method.

        Raises:
            Exception: Re-raises any exception that occurs during the database update process.
        """
        ad_groups = self.get_groups_from_ad()
        try:
            for group in ad_groups:
                self.sql_connection.session.merge(group)
            self.sql_connection.session.commit()
            self.logger.info('ADGroup table has been successfully updated')
        except Exception as e:
            self.sql_connection.session.rollback()
            self.logger.error('Rolling back changes, error: %s', e)
            raise e

    def get_groups_from_ad(
        self,
        search_filter: str = '(objectClass=group)',
        compatibility_mode: str | None = None,
    ) -> list[ADGroup]:
        """Retrieve groups from Active Directory based on a search filter.

        Args:
            search_filter (str): LDAP search filter. Defaults to '(objectClass=group)'

        Returns:
            list[ADGroup]: A list of ADGroup instances matching the search criteria.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        self.logger.debug("Using AD compatibility mode '%s' for get_groups_from_ad", effective_mode)

        return self._groups_from_search(search_filter)

    def _groups_from_search(self, search_filter: str) -> list[ADGroup]:
        """Run a group search and build validated ``ADGroup`` instances.

        Shared read path for group lookups: fetches via ``ad_connection.search``
        (which retries once on recoverable transport errors), annotates the
        group-type name, validates each record with ``ADGroupSchema``, and skips
        (logging) any record that fails validation rather than dropping silently.
        """

        attributes = ADGroup.get_attribute_list()
        ad_groups_dict = self.ad_connection.search(search_filter, attributes)
        ad_groups = []

        for group_data in ad_groups_dict:
            try:
                self.set_group_type_name(group_data)
                validated_data = ADGroupSchema(**group_data).model_dump()
                ad_groups.append(ADGroup(**validated_data))
            except ValidationError as e:
                self.logger.error(
                    "Validation error for group %s: %s",
                    group_data.get('distinguishedName'),
                    e,
                )

        return ad_groups

    def get_user_direct_groups(
        self,
        user: ADUser | str,
        compatibility_mode: str | None = None,
    ) -> list[ADGroup]:
        """Return the groups a user is a direct member of.

        Resolves the groups whose ``member`` attribute contains the user's
        distinguished name, i.e. direct (non-nested) memberships. Note that AD's
        ``member``/``memberOf`` linkage does not include a user's *primary*
        group; use :meth:`resolve_primary_group` for that.

        Args:
            user (ADUser | str): The user, or the user's distinguishedName.
            compatibility_mode (str | None): Optional per-call compatibility mode
                override (accepted for API symmetry; reads return typed models).

        Returns:
            list[ADGroup]: Direct group memberships (empty list if none).
        """

        effective_mode = self._resolve_effective_mode(compatibility_mode)
        self.logger.debug(
            "Using AD compatibility mode '%s' for get_user_direct_groups", effective_mode
        )

        user_dn = user.distinguishedName if isinstance(user, ADUser) else user
        if not user_dn:
            return []

        escaped_dn = escape_filter_chars(str(user_dn))
        search_filter = f"(&(objectClass=group)(member={escaped_dn}))"
        return self._groups_from_search(search_filter)

    @staticmethod
    def _derive_primary_group_sid(user_sid: str, primary_group_id: str) -> str | None:
        """Derive a primary group's SID from the user's SID and primary group RID.

        A user's primary group is not exposed via ``member``/``memberOf``. Its
        SID shares the domain portion of the user's ``objectSid`` with the RID
        replaced by ``primaryGroupID``. For example, user SID
        ``S-1-5-21-A-B-C-1105`` with ``primaryGroupID=513`` yields the group SID
        ``S-1-5-21-A-B-C-513``. Returns ``None`` when the user SID has no
        derivable domain portion.
        """

        if not user_sid or '-' not in user_sid:
            return None
        domain_sid = user_sid.rsplit('-', 1)[0]
        return f"{domain_sid}-{primary_group_id}"

    def resolve_primary_group(
        self,
        user: ADUser,
        compatibility_mode: str | None = None,
    ) -> ADGroup | None:
        """Resolve a user's primary group.

        A user's primary group is identified by ``primaryGroupID`` (a RID) and is
        not surfaced through the ``member``/``memberOf`` linkage. Because
        ``primaryGroupToken`` is a constructed attribute that cannot be evaluated
        in an LDAP search filter, the primary group's SID is derived from the
        user's ``objectSid`` (domain portion) and ``primaryGroupID`` (RID), then
        looked up via ``(&(objectClass=group)(objectSid=<sid>))``.

        Args:
            user (ADUser): The user whose ``objectSid`` and ``primaryGroupID`` are
                used to derive the primary group SID.
            compatibility_mode (str | None): Optional per-call compatibility mode
                override (accepted for API symmetry; reads return typed models).

        Returns:
            ADGroup | None: The primary group, or ``None`` when the user is
            missing ``objectSid``/``primaryGroupID`` or no group matches.
        """

        effective_mode = self._resolve_effective_mode(compatibility_mode)
        self.logger.debug(
            "Using AD compatibility mode '%s' for resolve_primary_group", effective_mode
        )

        user_sid = getattr(user, 'objectSid', None)
        primary_group_id = getattr(user, 'primaryGroupID', None)
        if not user_sid or not primary_group_id:
            self.logger.debug(
                "Cannot resolve primary group: missing objectSid/primaryGroupID (%s)",
                getattr(user, 'distinguishedName', user),
            )
            return None

        group_sid = self._derive_primary_group_sid(str(user_sid), str(primary_group_id))
        if not group_sid:
            self.logger.debug(
                "Cannot derive primary group SID from user objectSid '%s'", user_sid
            )
            return None

        escaped_sid = escape_filter_chars(group_sid)
        search_filter = f"(&(objectClass=group)(objectSid={escaped_sid}))"
        groups = self._groups_from_search(search_filter)
        return groups[0] if groups else None

    def modify_group(
        self,
        group: ADGroup,
        changes: list[tuple[str, Any]],
        compatibility_mode: str | None = None,
    ) -> dict[str, Any]:
        """Modify attributes of a group in Active Directory.

        Args:
            group (ADGroup): The group to modify.
            changes (list[tuple[str, Any]]): A list of attribute changes to apply.
                Each tuple consists of an attribute name and its new value.
                For example:
                    [
                        ('description', 'New Description'),
                        ('managedBy', 'CN=Manager,OU=Users,DC=example,DC=com'),
                    ]
            compatibility_mode (str | None): Optional per-call compatibility mode
                override controlling the response envelope shape.

        Returns:
            dict[str, Any]: A dictionary containing the result of the modify operation with the
            following keys:
                - 'success' (bool): Indicates whether the modification was successful.
                - 'result' (Any): Additional details about the operation result or error message.
                - 'changes' (dict[str, Any]): A mapping of attribute names to their changes in the
                format 'old_value -> new_value'.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        change_affects = {k: f"{getattr(group, k)} -> {v}" for k, v in changes}
        try:
            response = self.ad_connection.modify(group.distinguishedName, changes)
        except LDAPException as e:
            self.logger.error(
                "Exception occurred while modifying group %s: changes: %s error msg: %s",
                group.distinguishedName,
                change_affects,
                str(e),
            )
            return finalize_ad_write_response(
                {'success': False, 'result': str(e)},
                effective_mode=effective_mode,
                exception=e,
                retry_telemetry=self.ad_connection.last_retry_telemetry,
            )

        if response is None:
            self.logger.warning(
                "Update got no response when trying to modify %s: changes: %s",
                group.distinguishedName,
                change_affects,
            )
        elif response.get("success", False):
            self.logger.info("Updated %s: changes: %s", group.distinguishedName, change_affects)
        else:
            self.logger.warning(
                "Failed to update AD group: %s\n\tResponse details: %s\n\tChanges: %s",
                group.distinguishedName,
                response.get("result"),
                change_affects,
            )
        return finalize_ad_write_response(
            {
                'success': response.get('success', False),
                'result': response.get('result'),
                'changes': change_affects,
            },
            effective_mode=effective_mode,
            retry_telemetry=self.ad_connection.last_retry_telemetry,
        )

    @staticmethod
    def attributes() -> list[str]:
        """Get the list of attributes for ADGroup.

        Returns:
            list[str]: The list of attributes.
        """
        return ADGroup.get_attribute_list()
