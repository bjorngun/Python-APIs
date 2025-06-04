"""
Module providing the ADGroupService class for interacting with Active Directory groups.
"""

# pylint: disable=duplicate-code

from logging import getLogger
import os
from typing import Any

from ldap3.core.exceptions import LDAPException
from pydantic import ValidationError

from dev_tools import timing_decorator
from python_apis.apis import ADConnection, SQLConnection
from python_apis.models import ADGroup, base
from python_apis.schemas import ADGroupSchema

class ADGroupService:
    """Service class for interacting with Active Directory groups.
    """

    def __init__(self, ad_connection: ADConnection = None, sql_connection: SQLConnection = None,
                 ldap_logging: bool = False):
        """Initialize the ADGroupService with an ADConnection and a db connection.

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

    def get_groups_from_ad(self, search_filter: str = '(objectClass=group)'
                           ) -> list[ADGroup]:
        """Retrieve groups from Active Directory based on a search filter.

        Args:
            search_filter (str): LDAP search filter. Defaults to '(objectClass=group)'

        Returns:
            list[ADGroup]: A list of ADGroup instances matching the search criteria.
        """
        attributes = ADGroup.get_attribute_list()
        ad_groups_dict = self.ad_connection.search(search_filter, attributes)
        ad_groups = []

        for group_data in ad_groups_dict:
            try:
                self.set_group_type_name(group_data)
                # Validate and parse data using Pydantic model
                validated_data = ADGroupSchema(**group_data).model_dump()
                # Create ADGroup instance
                ad_group = ADGroup(**validated_data)
                ad_groups.append(ad_group)
            except ValidationError as e:
                # Handle validation errors
                self.logger.error(
                    "Validation error for group %s: %s",
                    group_data.get('distinguishedName'),
                    e
                )

        return ad_groups

    def modify_group(
        self, group: ADGroup, changes: list[tuple[str, Any]]) -> dict[str, Any]:
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

        Returns:
            dict[str, Any]: A dictionary containing the result of the modify operation with the
            following keys:
                - 'success' (bool): Indicates whether the modification was successful.
                - 'result' (Any): Additional details about the operation result or error message.
                - 'changes' (dict[str, Any]): A mapping of attribute names to their changes in the
                format 'old_value -> new_value'.
        """
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
            return {'success': False, 'result': str(e)}

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
        return {
            'success': response.get('success', False),
            'result': response.get('result'),
            'changes': change_affects,
        }

    @staticmethod
    def attributes() -> list[str]:
        """Get the list of attributes for ADGroup.

        Returns:
            list[str]: The list of attributes.
        """
        return ADGroup.get_attribute_list()
