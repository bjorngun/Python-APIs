"""
Module providing the ADOrganizationalUnitService class for interacting with Active Directory
organizational units.
"""

# pylint: disable=duplicate-code

from logging import getLogger
import os
from typing import Any, Optional

from ldap3.core.exceptions import LDAPException
from pydantic import ValidationError

from dev_tools import timing_decorator
from python_apis.apis import ADConnection, SQLConnection
from python_apis.models import ADOrganizationalUnit, base
from python_apis.schemas import ADOrganizationalUnitSchema

class ADOrganizationalUnitService:
    """Service class for interacting with Active Directory organizational units.
    """

    def __init__(self, ad_connection: ADConnection = None, sql_connection: SQLConnection = None,
                 ldap_logging: bool = False):
        """Initialize the ADOrganizationalUnitService with an ADConnection and a db connection.

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
        """Create the ADOrganizationalUnit table in the database if it does not exist."""
        base.Base.metadata.create_all(
            self.sql_connection.engine, tables=[ADOrganizationalUnit.__table__], checkfirst=True)

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
    def set_ou_children_and_parent(self, ad_ous: dict[str, ADOrganizationalUnit]) -> None:
        """Set the parent and children relationships for organizational units.

        Args:
            ad_ous (dict[str, ADOrganizationalUnit]): A dictionary mapping distinguished names to
                ADOrganizationalUnit instances.
        """
        for ou in ad_ous.values():
            if ou.parseDistinguishedName in ad_ous:
                parent_ou = ad_ous[ou.parseDistinguishedName]

                # Set up the child relation
                if ou.children is None:
                    ou.children = []
                if parent_ou.children is None:
                    parent_ou.children = []
                parent_ou.children.append(ou)

                # Set up the parent relation
                ou.parent = parent_ou

    def get_deepest_ou_field(
        self, ou: ADOrganizationalUnit, field: str, default_value: Optional[str] = None):
        """Recursively get the value of a field from the deepest organizational unit.

        Args:
            ou (ADOrganizationalUnit): The starting organizational unit.
            field (str): The field name to retrieve.
            default_value (Optional[str], optional): The default value to return if the field is
            not found.
                Defaults to None.

        Returns:
            Any: The value of the field from the deepest organizational unit, or default_value if
            not found.
        """
        if not ou:
            return default_value
        ou_field_value = getattr(ou, field)
        if field == 'description' and isinstance(ou_field_value, str):
            if ou_field_value.isdigit():
                return ou_field_value
        if ou_field_value and len(ou_field_value) > 0:
            return ou_field_value
        return self.get_deepest_ou_field(ou.parent, field, default_value)

    @timing_decorator
    def get_ous_from_db(self) -> list[ADOrganizationalUnit]:
        """Retrieve organizational units from database.

        Returns:
            list[ADOrganizationalUnit]: A list of all ADOrganizationalUnit in the database.
        """

        ad_ous = self.sql_connection.session.query(ADOrganizationalUnit).all()
        return ad_ous

    @timing_decorator
    def update_ou_db(self):
        """
        Update the organizational unit database with the latest organizational units from Active
        Directory.

        This method performs the following actions:

        1. Retrieves all organizational units entries from Active Directory by calling
        `get_ous_from_ad()`.
        2. Deletes all existing `ADOrganizationalUnit` records from the local database.
        3. Adds the newly fetched organizational units to the database session.
        4. Commits the transaction to save the changes to the database.

        If an exception occurs during the database operations, the method will:

        - Roll back the current transaction to prevent partial commits.
        - Log an error message with details about the exception.
        - Re-raise the original exception to be handled by the calling code.

        Note:
            - This method is decorated with `@timing_decorator`, which measures and logs the
            execution time.
            - Ensure that the database connection is properly configured and active before calling
            this method.

        Raises:
            Exception: Re-raises any exception that occurs during the database update process.

        """
        ad_ous = self.get_ous_from_ad()
        try:
            self.sql_connection.session.query(ADOrganizationalUnit).delete()
            self.sql_connection.session.commit()

            self.sql_connection.session.add_all(ad_ous)
            self.sql_connection.session.commit()
            self.logger.info('ADOrganizationalUnit table has been successfully updated')
        except Exception as e:
            self.sql_connection.session.rollback()
            self.logger.error('Rolling back changes, error: %s', e)
            raise e

    def get_ous_from_ad(self, search_filter: str = '(objectClass=organizationalUnit)'
                        ) -> list[ADOrganizationalUnit]:
        """Retrieve organizational units from Active Directory based on a search filter.

        Args:
            search_filter (str): LDAP search filter. Defaults to '(objectClass=organizationalUnit)'

        Returns:
            list[ADOrganizationalUnit]: A list of ADOrganizationalUnit instances matching the
            search criteria.
        """
        attributes = ADOrganizationalUnit.get_attribute_list()
        ad_ous_dict = self.ad_connection.search(search_filter, attributes)
        ad_ous = []

        for ou_data in ad_ous_dict:
            try:
                # Validate and parse data using Pydantic model
                validated_data = ADOrganizationalUnitSchema(**ou_data).model_dump()
                # Create ADOrganizationalUnit instance
                ad_ou = ADOrganizationalUnit(**validated_data)
                ad_ous.append(ad_ou)
            except ValidationError as e:
                # Handle validation errors
                self.logger.error(
                    "Validation error for ou %s: %s",
                    ou_data.get('distinguishedName'),
                    e
                )

        return ad_ous

    def modify_ou(
        self, ou: ADOrganizationalUnit, changes: list[tuple[str, str]]) -> dict[str, Any]:
        """Modify attributes of a organizational unit in Active Directory.

        Args:
            ou (ADOrganizationalUnit): The organizational unit to modify.
            changes (list[tuple[str, str]]): A list of attribute changes to apply.
                Each tuple consists of an attribute name and its new value.
                For example:
                    [('name', 'John'), ('description', 'Doe')]

        Returns:
            dict[str, Any]: A dictionary containing the result of the modify operation with the
            following keys:
                - 'success' (bool): Indicates whether the modification was successful.
                - 'result' (Any): Additional details about the operation result or error message.
                - 'changes' (dict[str, str]): A mapping of attribute names to their changes in the
                format 'old_value -> new_value'.
        """
        change_affects = {k: f"{getattr(ou, k)} -> {v}" for k, v in changes}
        try:
            response = self.ad_connection.modify(ou.distinguishedName, changes)
        except LDAPException as e:
            self.logger.error(
                "Exception occurred while modifying org unit %s: changes: %s error msg: %s",
                ou.distinguishedName,
                change_affects,
                str(e),
            )
            return {'success': False, 'result': str(e)}

        if response is None:
            self.logger.warning(
                "Update got no response when trying to modify %s: changes: %s",
                ou.distinguishedName,
                change_affects,
            )
        elif response.get("success", False):
            self.logger.info("Updated %s: changes: %s", ou.distinguishedName, change_affects)
        else:
            self.logger.warning(
                "Failed to update AD org unit: %s\n\tResponse details: %s\n\tChanges: %s",
                ou.distinguishedName,
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
        """Get the list of attributes for ADOrganizationalUnit.

        Returns:
            list[str]: The list of attributes.
        """
        return ADOrganizationalUnit.get_attribute_list()
