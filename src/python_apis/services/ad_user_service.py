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

class ADUserService:
    """Service class for interacting with Active Directory users.
    """

    def __init__(self, ad_connection: ADConnection = None, sql_connection: SQLConnection = None,
                 ldap_logging: bool = False):
        """Initialize the ADUserService with an ADConnection and an SQLConnection.

        Args:
            ad_connection (ADConnection, optional): An existing ADConnection instance.
                If None, a new one will be created.
            sql_connection (SQLConnection, optional): An existing SQLConnection instance.
                If None, a new one will be created.
            ldap_logging (bool, optional): Whether to enable LDAP logging. Defaults to False.
        """
        self.logger = getLogger(__name__)

        if sql_connection is None:
            sql_connection = self._get_sql_connection()
        self.sql_connection = sql_connection

        if ad_connection is None:
            ad_connection = self._get_ad_connection(ldap_logging)
        self.ad_connection = ad_connection

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

    def get_users_from_ad(self, search_filter: str = '(objectClass=user)') -> list[ADUser]:
        """Retrieve users from Active Directory based on a search filter.

        Args:
            search_filter (str): LDAP search filter. Defaults to '(objectClass=user)'.

        Returns:
            list[ADUser]: A list of ADUser instances matching the search criteria.
        """
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

    def add_member(self, user: ADUser, group_dn: str) -> dict[str, Any]:
        """Add a user to an Active Directory group.

        Args:
            user (ADUser): The user to add.
            group_dn (str): The distinguished name of the group.

        Returns:
            dict[str, Any]: The result of the add operation.
        """
        return self.ad_connection.add_member(user.distinguishedName, group_dn)

    def remove_member(self, user: ADUser, group_dn: str) -> dict[str, Any]:
        """Remove a user from an Active Directory group.

        Args:
            user (ADUser): The user to remove.
            group_dn (str): The distinguished name of the group.

        Returns:
            dict[str, Any]: The result of the remove operation.
        """
        return self.ad_connection.remove_member(user.distinguishedName, group_dn)

    def modify_user(self, user: ADUser, changes: list[tuple[str, str]]) -> dict[str, Any]:
        """Modify attributes of a user in Active Directory.

        Args:
            user (ADUser): The user to modify.
            changes (list[tuple[str, str]]): A list of attribute changes to apply.
                Each tuple consists of an attribute name and its new value.
                For example:
                    [('givenName', 'John'), ('sn', 'Doe')]

        Returns:
            dict[str, Any]: A dictionary containing the result of the modify operation with the
            following keys:
                - 'success' (bool): Indicates whether the modification was successful.
                - 'result' (Any): Additional details about the operation result or error message.
                - 'changes' (dict[str, str]): A mapping of attribute names to their changes in the
                format 'old_value -> new_value'.
        """
        change_affects = {k: f"{getattr(user, k)} -> {v}" for k, v in changes}
        try:
            response = self.ad_connection.modify(user.distinguishedName, changes)
        except LDAPException as e:
            self.logger.error(
                "Exception occurred while modifying user %s: changes: %s error msg: %s",
                user.sAMAccountName,
                change_affects,
                str(e),
            )
            return {'success': False, 'result': str(e)}

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
        return {
            'success': response.get('success', False),
            'result': response.get('result'),
            'changes': change_affects,
        }

    @staticmethod
    def attributes() -> list[str]:
        """Get the list of attributes for ADUser.

        Returns:
            list[str]: The list of attributes.
        """
        return ADUser.get_attribute_list()
