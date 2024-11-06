"""
Module providing the ADUserService class for interacting with Active Directory users.
"""

from logging import getLogger
import json
import os
from os import getenv
from typing import Any, Optional

from ldap3.core.exceptions import LDAPException
from pydantic import ValidationError

from dev_tools import timing_decorator
from python_apis.apis import ADConnection, SQLConnection
from python_apis.models import ADUser
from python_apis.schemas import ADUserSchema

class ADUserService:
    """Service class for interacting with Active Directory users.

    Attributes:
        _attributes_cache (Optional[list[str]]): Cache for standard attributes.
        _attributes_extended_cache (Optional[list[str]]): Cache for extended attributes.
    """

    _attributes_cache: Optional[list[str]] = None
    _attributes_extended_cache: Optional[list[str]] = None

    def __init__(self, ad_connection: ADConnection = None, sql_connection: SQLConnection = None):
        """Initialize the ADUserService with an ADConnection.

        Args:
            ad_connection (ADConnection, optional): An existing ADConnection instance.
                If None, a new one will be created.
        """
        self.logger = getLogger(__name__)

        if sql_connection is None:
            sql_connection = self._get_sql_connection()
        self.sql_connection = sql_connection

        if ad_connection is None:
            ad_connection = self._get_ad_connection()
        self.ad_connection = ad_connection

    def _get_sql_connection(self) -> SQLConnection:
        return SQLConnection(
            server=getenv('ADUSER_DB_SERVER'),
            database=getenv('ADUSER_DB_NAME'),
            driver=getenv('ADUSER_SQL_DRIVER'),
        )

    @timing_decorator
    def _get_ad_connection(self) -> ADConnection:
        """Create and return an ADConnection instance.

        Returns:
            ADConnection: A new ADConnection instance based on environment variables.
        """
        ad_servers = os.getenv("LDAP_SERVER_LIST").split()
        search_base = os.getenv("SEARCH_BASE")
        ad_connection = ADConnection(ad_servers, search_base)
        return ad_connection

    @timing_decorator
    def get_users(self) -> list[ADUser]:
        """Retrieve users from database.

        Returns:
            list[ADUser]: A list of all ADUser in the database.
        """

        ad_users = self.sql_connection.session.query(ADUser).all()
        return ad_users

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
    def _load_attributes(filename: str, cache_attr: str) -> list[str]:
        """Load attributes from a JSON file and cache them.

        Args:
            filename (str): The name of the JSON file containing the attributes.
            cache_attr (str): The name of the cache attribute.

        Returns:
            list[str]: The list of attributes loaded from the file.

        Raises:
            FileNotFoundError: If the JSON file is not found.
            ValueError: If there is an error decoding the JSON file.
        """
        cache = getattr(ADUserService, cache_attr)
        if cache is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_file_path = os.path.join(current_dir, filename)

            try:
                with open(json_file_path, 'r', encoding='UTF-8') as f:
                    cache = json.load(f)
                    setattr(ADUserService, cache_attr, cache)
            except FileNotFoundError as e:
                raise FileNotFoundError(f"JSON file not found at {json_file_path}") from e
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding JSON file '{filename}': {e}") from e


        return cache

    @staticmethod
    def attributes(extended: bool = False) -> list[str]:
        """Get the list of attributes for ADUser.

        Args:
            extended (bool): If True, load extended attributes. Defaults to False.

        Returns:
            list[str]: The list of attributes.
        """
        if extended:
            cache_attr = '_attributes_extended_cache'
            filename = 'ad_user_attributes_extended.json'
        else:
            cache_attr = '_attributes_cache'
            filename = 'ad_user_attributes.json'
        return ADUserService._load_attributes(filename, cache_attr)
