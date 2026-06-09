"""
Module providing the ADUserService class for interacting with Active Directory users.
"""

# pylint: disable=duplicate-code

from logging import getLogger
import os
from typing import Any

from ldap3.core.exceptions import LDAPException
from pydantic import ValidationError

from dev_tools import timing_decorator
from python_apis.apis import ADConnection, SQLConnection
from python_apis.models import ADUser
from python_apis.schemas import ADUserSchema
from python_apis.services.compatibility_mode import (
    finalize_ad_write_response,
    resolve_service_compatibility_mode,
)

class ADUserService:
    """Service class for interacting with Active Directory users.

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
        """Initialize the ADUserService with an ADConnection and an SQLConnection.

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

    def _finalize_write(
        self,
        legacy_response: dict[str, Any],
        *,
        effective_mode: str,
        exception: BaseException | None = None,
    ) -> dict[str, Any]:
        """Shape a write-operation response for the effective compatibility mode.

        Thin wrapper over
        :func:`python_apis.services.compatibility_mode.finalize_ad_write_response`
        so all AD services share one envelope/legacy-mirroring implementation.
        Retry telemetry captured by the most recent AD operation is surfaced on
        the envelope.
        """

        return finalize_ad_write_response(
            legacy_response,
            effective_mode=effective_mode,
            exception=exception,
            retry_telemetry=self.ad_connection.last_retry_telemetry,
        )

    def get_compatibility_mode(self, compatibility_mode: str | None = None) -> dict[str, str]:
        """Return service default and effective compatibility mode for this context."""
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        return {
            'service_default_mode': self.compatibility_mode,
            'effective_mode': effective_mode,
        }

    def _get_sql_connection(self) -> SQLConnection:
        return SQLConnection(
            server=os.getenv('AD_DB_SERVER', os.getenv('DEFAULT_DB_SERVER')),
            database=os.getenv('AD_DB_NAME', os.getenv('DEFAULT_DB_NAME')),
            driver=os.getenv('AD_SQL_DRIVER', os.getenv('DEFAULT_SQL_DRIVER')),
        )

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
    def get_users_from_db(self) -> list[ADUser]:
        """Retrieve users from database.

        Returns:
            list[ADUser]: A list of all ADUser in the database.
        """

        ad_users = self.sql_connection.session.query(ADUser).all()
        return ad_users

    @timing_decorator
    def update_user_db(self):
        """
        Update the local user database with the latest users from Active Directory.

        This method performs the following actions:

        1. Retrieves all user entries from Active Directory by calling `get_users_from_ad()`.
        2. Deletes all existing `ADUser` records from the local database.
        3. Adds the newly fetched users to the database session.
        4. Commits the transaction to save the changes to the database.

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
        ad_users = self.get_users_from_ad()
        try:
            self.sql_connection.session.query(ADUser).delete()

            self.sql_connection.session.add_all(ad_users)
            self.sql_connection.session.commit()
        except Exception as e:
            self.sql_connection.session.rollback()
            self.logger.error('Rolling back changes, error: %s', e)
            raise e

    def get_users_from_ad(
        self,
        search_filter: str = '(objectClass=user)',
        compatibility_mode: str | None = None,
    ) -> list[ADUser]:
        """Retrieve users from Active Directory based on a search filter.

        Args:
            search_filter (str): LDAP search filter. Defaults to '(objectClass=user)'.

        Returns:
            list[ADUser]: A list of ADUser instances matching the search criteria.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        self.logger.debug("Using AD compatibility mode '%s' for get_users_from_ad", effective_mode)

        attributes = ADUser.get_attribute_list()
        ad_users_dict = self.ad_connection.search(search_filter, attributes)
        ad_users = []

        for user_data in ad_users_dict:
            try:
                # Validate and parse data using Pydantic model
                validated_data = ADUserSchema(**user_data).model_dump()
                # Create ADUser instance
                ad_user = ADUser(**validated_data)
                ad_users.append(ad_user)
            except ValidationError as e:
                # Handle validation errors
                self.logger.error(
                    "Validation error for user %s: %s",
                    user_data.get('sAMAccountName'),
                    e
                )

        #ad_users = [ADUser(**x) for x in ad_users_dict]
        return ad_users

    def get_all_sam_account_names(
        self,
        search_filter: str = '(objectClass=user)',
        compatibility_mode: str | None = None,
    ) -> set[str]:
        """Retrieve all sAMAccountName values from Active Directory.

        Returns:
            set[str]: A set of all sAMAccountName values.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        self.logger.debug(
            "Using AD compatibility mode '%s' for get_all_sam_account_names",
            effective_mode,
        )

        attributes = ['sAMAccountName']
        ad_users_dict = self.ad_connection.search(search_filter, attributes)
        sam_account_names = {str(user.get('sAMAccountName')) for user
                             in ad_users_dict if 'sAMAccountName' in user}
        return sam_account_names

    def enable_user(
        self, user: ADUser | str, compatibility_mode: str | None = None
    ) -> dict[str, Any]:
        """Enable an Active Directory user.

        Args:
            user (ADUser | str): The user (or distinguishedName) to enable.
            compatibility_mode (str | None): Optional per-call compatibility mode
                override controlling the response envelope shape.

        Returns:
            dict[str, Any]: The result of the enable operation.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        distinguished_name = (user.distinguishedName
                              if isinstance(user, ADUser)
                              else str(user))
        response = self.ad_connection.enable_user(distinguished_name)
        return self._finalize_write(response, effective_mode=effective_mode)

    def disable_user(
        self, user: ADUser | str, compatibility_mode: str | None = None
    ) -> dict[str, Any]:
        """Disable an Active Directory user.

        Args:
            user (ADUser | str): The user (or distinguishedName) to disable.
            compatibility_mode (str | None): Optional per-call compatibility mode
                override controlling the response envelope shape.

        Returns:
            dict[str, Any]: The result of the disable operation.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        distinguished_name = (user.distinguishedName
                              if isinstance(user, ADUser)
                              else str(user))
        response = self.ad_connection.disable_user(distinguished_name)
        return self._finalize_write(response, effective_mode=effective_mode)

    def add_member(
        self, user: ADUser, group_dn: str, compatibility_mode: str | None = None
    ) -> dict[str, Any]:
        """Add a user to an Active Directory group.

        Args:
            user (ADUser): The user to add.
            group_dn (str): The distinguished name of the group.
            compatibility_mode (str | None): Optional per-call compatibility mode
                override controlling the response envelope shape.

        Returns:
            dict[str, Any]: The result of the add operation.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        response = self.ad_connection.add_member(user.distinguishedName, group_dn)
        return self._finalize_write(response, effective_mode=effective_mode)

    def remove_member(
        self, user: ADUser, group_dn: str, compatibility_mode: str | None = None
    ) -> dict[str, Any]:
        """Remove a user from an Active Directory group.

        Args:
            user (ADUser): The user to remove.
            group_dn (str): The distinguished name of the group.
            compatibility_mode (str | None): Optional per-call compatibility mode
                override controlling the response envelope shape.

        Returns:
            dict[str, Any]: The result of the remove operation.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        response = self.ad_connection.remove_member(user.distinguishedName, group_dn)
        return self._finalize_write(response, effective_mode=effective_mode)

    def move_user_to_ou(
        self, user: ADUser, target_ou_dn: str, compatibility_mode: str | None = None
    ) -> dict[str, Any]:
        """Move a user to a different OU in Active Directory.

        Args:
            user (ADUser): The user to move.
            target_ou_dn (str): Distinguished name for the destination OU.
            compatibility_mode (str | None): Optional per-call compatibility mode
                override controlling the response envelope shape.

        Returns:
            dict[str, Any]: Result payload from the move operation including success flag.
        """

        effective_mode = self._resolve_effective_mode(compatibility_mode)
        current_dn = user.distinguishedName
        try:
            response = self.ad_connection.move_entry(str(current_dn), target_ou_dn)
        except LDAPException as e:
            self.logger.error(
                "Exception occurred while moving user %s to %s: %s",
                getattr(user, 'sAMAccountName', '<unknown>'),
                target_ou_dn,
                str(e),
            )
            return self._finalize_write(
                {'success': False, 'result': str(e)},
                effective_mode=effective_mode,
                exception=e,
            )

        result = dict(response) if response is not None else {'success': False, 'result': None}
        if not result.get('success'):
            self.logger.warning(
                "Failed to move AD user %s to %s: %s",
                getattr(user, 'sAMAccountName', '<unknown>'),
                target_ou_dn,
                result.get('result'),
            )
            return self._finalize_write(result, effective_mode=effective_mode)

        new_dn = self._user_dn(str(user.cn), target_ou_dn)
        setattr(user, 'distinguishedName', new_dn)
        setattr(user, 'ou', target_ou_dn)
        result['dn'] = new_dn
        self.logger.info(
            "Moved %s to new OU %s",
            getattr(user, 'sAMAccountName', '<unknown>'),
            target_ou_dn,
        )
        return self._finalize_write(result, effective_mode=effective_mode)

    def modify_user(
        self,
        user: ADUser,
        changes: list[tuple[str, str]],
        compatibility_mode: str | None = None,
    ) -> dict[str, Any]:
        """Modify attributes of a user in Active Directory.

        Args:
            user (ADUser): The user to modify.
            changes (list[tuple[str, str]]): A list of attribute changes to apply.
                Each tuple consists of an attribute name and its new value.
                For example:
                    [('givenName', 'John'), ('sn', 'Doe')]
            compatibility_mode (str | None): Optional per-call compatibility mode
                override controlling the response envelope shape.

        Returns:
            dict[str, Any]: A dictionary containing the result of the modify operation with the
            following keys:
                - 'success' (bool): Indicates whether the modification was successful.
                - 'result' (Any): Additional details about the operation result or error message.
                - 'changes' (dict[str, str]): A mapping of attribute names to their changes in the
                format 'old_value -> new_value'.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        change_affects = {k: f"{getattr(user, k)} -> {v}" for k, v in changes}
        try:
            response = self.ad_connection.modify(user.distinguishedName, changes)
            for k, v in changes:
                setattr(user, k, v)
        except LDAPException as e:
            self.logger.error(
                "Exception occurred while modifying user %s: changes: %s error msg: %s",
                user.sAMAccountName,
                change_affects,
                str(e),
            )
            return self._finalize_write(
                {'success': False, 'result': str(e)},
                effective_mode=effective_mode,
                exception=e,
            )

        if response is None:
            self.logger.warning(
            "Updated got no response when trying to modify %s: changes: %s",
            user.sAMAccountName,
            change_affects,
        )
        elif response.get("success", False):
            self.logger.info("Updated %s: changes: %s", user.sAMAccountName, change_affects)
        else:
            self.logger.warning(
                "Failed to update AD user: %s\n\tResponse details: %s\n\tChanges: %s",
                user.sAMAccountName,
                response.get("result"),
                change_affects,
            )
        return self._finalize_write(
            {
                'success': response.get('success', False),
                'result': response.get('result'),
                'changes': change_affects,
            },
            effective_mode=effective_mode,
        )

    @staticmethod
    def attributes() -> list[str]:
        """Get the list of attributes for ADUser.

        Returns:
            list[str]: The list of attributes.
        """
        return ADUser.get_attribute_list()


    # ---------------------------------------------------------------------
    # Create new user
    # ---------------------------------------------------------------------
    # in ADUserService (ad_user_service.py)

    def _user_dn(self, cn: str, ou_dn: str) -> str:
        return f"CN={cn},{ou_dn}"

    def set_password(
        self,
        user: ADUser | str,
        new_password: str,
        *,
        must_change_at_next_logon: bool = False,
        compatibility_mode: str | None = None,
    ) -> dict[str, Any]:
        """Set a new password for the specified user.

        Args:
            user (ADUser | str): The user (or distinguishedName) for whom to set the password.
            new_password (str): The new password to set.
            must_change_at_next_logon (bool): If True, forces the user to change
                their password at the next logon. Defaults to False.
            compatibility_mode (str | None): Optional per-call compatibility mode
                override controlling the response envelope shape.

        Returns:
            dict[str, Any]: Result payload with 'success' and 'result' keys.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        distinguished_name = (user.distinguishedName
                              if isinstance(user, ADUser)
                              else str(user))
        account_label = (getattr(user, 'sAMAccountName', None)
                         if isinstance(user, ADUser)
                         else None) or distinguished_name
        try:
            response = self.ad_connection.set_password(str(distinguished_name), new_password)
            if not response.get('success'):
                self.logger.warning("Failed to set password for user %s: %s", account_label,
                                    response.get('result'))
                return self._finalize_write(
                    {'success': False, 'result': response.get('result')},
                    effective_mode=effective_mode,
                )

            if must_change_at_next_logon:
                force_resp = self.ad_connection.force_change_password_at_next_logon(
                    str(distinguished_name), force=True
                )
                if not force_resp.get('success'):
                    self.logger.warning(
                        "Failed to set 'must change password' for user %s: %s",
                        account_label, force_resp.get('result')
                    )
                    return self._finalize_write(
                        {
                            'success': False,
                            'result': {
                                'password': response.get('result'),
                                'must_change': force_resp.get('result'),
                            },
                        },
                        effective_mode=effective_mode,
                    )
        except LDAPException as e:
            self.logger.error("Exception occurred while setting password for user %s: %s",
                              account_label, str(e))
            return self._finalize_write(
                {'success': False, 'result': str(e)},
                effective_mode=effective_mode,
                exception=e,
            )

        self.logger.info("Successfully set password for user %s", account_label)
        return self._finalize_write(
            {'success': True, 'result': response.get('result')},
            effective_mode=effective_mode,
        )

    def create_user(  # pylint: disable=too-many-locals
        self,
        cn: str,
        ou_dn: str,
        attrs: dict[str, object],
        **options: Any,
    ) -> dict[str, Any]:
        """
        Create a user in AD under `ou_dn` with a Common Name `cn`.

        Required:
            - attrs['objectClass'] should include 'user'
            - attrs should include minimal identity fields
                (e.g., sAMAccountName, userPrincipalName, sn, givenName, displayName)
        Optional:
            - set_password: if provided, sets the password post-create
            - must_change_password_at_next_logon: if True, forces password change
                at next logon (only applies when set_password is provided)
            - enable_after_create: if True, enables the user after create
                (requires password set first in most setups)
            - compatibility_mode: optional per-call compatibility mode override
                controlling the response envelope shape
        """
        set_password = options.get('set_password')
        must_change_password = options.get('must_change_password_at_next_logon', False)
        enable_after_create = options.get('enable_after_create', False)
        unexpected_options = set(options) - {
            'set_password', 'must_change_password_at_next_logon', 'enable_after_create',
            'compatibility_mode',
        }
        if unexpected_options:
            raise ValueError(f"Unsupported options provided: {sorted(unexpected_options)}")

        effective_mode = self._resolve_effective_mode(options.get('compatibility_mode'))
        dn = self._user_dn(cn, ou_dn)

        # Build attributes for creation (objectClass MUST be present on add)
        create_attrs = dict(attrs)
        if 'objectClass' not in create_attrs:
            create_attrs['objectClass'] = ['top', 'person', 'organizationalPerson', 'user']

        try:
            response = self.ad_connection.add_entry(dn, create_attrs)
        except LDAPException as e:
            self.logger.error("Failed to create AD user CN=%s in %s: %s", cn, ou_dn, e)
            return self._finalize_write(
                {'success': False, 'result': str(e), 'dn': dn},
                effective_mode=effective_mode,
                exception=e,
            )

        if not response.get('success'):
            self.logger.warning("Create user failed for %s: %s", dn, response.get('result'))
            return self._finalize_write(
                {'success': False, 'result': response.get('result'), 'dn': dn},
                effective_mode=effective_mode,
            )

        # Optional: set password then enable. Internal sub-operations are pinned
        # to legacy mode so their `result`/`success` keys are always present for
        # the partial-failure aggregation below, regardless of the effective mode.
        if set_password:
            pw_resp = self.set_password(
                dn, set_password, must_change_at_next_logon=must_change_password,
                compatibility_mode='legacy',
            )
            if not pw_resp.get('success'):
                self.logger.warning("Set password failed for %s: %s", dn, pw_resp.get('result'))
                # You may choose to return failure or proceed; here we surface partial failure:
                return self._finalize_write(
                    {
                        'success': False,
                        'result': {
                            'create': response.get('result'),
                            'password': pw_resp.get('result')
                        },
                        'dn': dn,
                    },
                    effective_mode=effective_mode,
                )

        if enable_after_create:
            en_resp = self.enable_user(dn, compatibility_mode='legacy')
            if not en_resp.get('success'):
                self.logger.warning("Enable user failed for %s: %s", dn, en_resp.get('result'))
                return self._finalize_write(
                    {
                        'success': False,
                        'result': {'create': response.get('result'),
                                   'enable': en_resp.get('result')},
                        'dn': dn,
                    },
                    effective_mode=effective_mode,
                )

        self.logger.info("Created AD user: %s", dn)
        return self._finalize_write(
            {'success': True, 'result': response.get('result'), 'dn': dn},
            effective_mode=effective_mode,
        )

    def rename_user_cn(
        self, user: ADUser, new_cn: str, compatibility_mode: str | None = None
    ) -> dict[str, Any]:
        """
        Rename the user's CN (relative DN) without changing their OU placement.

        Args:
            user: The ADUser to rename.
            new_cn: The new common name for the user.
            compatibility_mode: Optional per-call compatibility mode override
                controlling the response envelope shape.

        Returns:
            Dictionary containing the result of the rename operation.
        """
        effective_mode = self._resolve_effective_mode(compatibility_mode)
        current_dn = getattr(user, "distinguishedName", None)
        if not current_dn:
            return self._finalize_write(
                {"success": False, "result": "User distinguishedName unavailable"},
                effective_mode=effective_mode,
            )

        # Extract the current OU from the DN (everything after the first comma)
        dn_parts = current_dn.split(',', 1)
        if len(dn_parts) < 2:
            return self._finalize_write(
                {"success": False, "result": "Invalid distinguishedName format"},
                effective_mode=effective_mode,
            )

        current_ou = dn_parts[1]
        new_relative_dn = f"CN={new_cn}"
        new_full_dn = f"{new_relative_dn},{current_ou}"

        # Log the operation
        old_cn = getattr(user, "cn", "<unknown>")
        sam_account = getattr(user, "sAMAccountName", "<unknown>")

        try:
            response = self.ad_connection.rename_dn(current_dn, new_relative_dn)
        except LDAPException as e:
            self.logger.error(
                "Exception occurred while renaming user %s (CN: %s -> %s): %s",
                sam_account,
                old_cn,
                new_cn,
                str(e),
            )
            return self._finalize_write(
                {'success': False, 'result': str(e)},
                effective_mode=effective_mode,
                exception=e,
            )

        result = dict(response) if response is not None else {'success': False, 'result': None}

        if not result.get('success'):
            self.logger.warning(
                "Failed to rename AD user %s (CN: %s -> %s): %s",
                sam_account,
                old_cn,
                new_cn,
                result.get('result'),
            )
            return self._finalize_write(result, effective_mode=effective_mode)

        # Update the user object with the new DN and CN
        setattr(user, 'distinguishedName', new_full_dn)
        setattr(user, 'cn', new_cn)
        result['old_dn'] = current_dn
        result['new_dn'] = new_full_dn
        result['old_cn'] = old_cn
        result['new_cn'] = new_cn

        self.logger.info(
            "Successfully renamed user %s from CN=%s to CN=%s",
            sam_account,
            old_cn,
            new_cn,
        )

        return self._finalize_write(result, effective_mode=effective_mode)
