"""This module contains the functionality concerning the
connection and the methods that gets data from AD and can modify the AD.

This module was build as an "in the same domain" AD connection and has no plans
to extend to being able to connect through a custom user and password. Hence
this package will need a user that has the required permissions to edit/read the
AD to run it effectively.
"""

import collections
import ssl
from typing import Any, Dict, List

from dacite import from_dict
from ldap3 import (ALL_ATTRIBUTES, KERBEROS, MODIFY_ADD, MODIFY_DELETE, MOCK_SYNC,
                   MODIFY_REPLACE, ROUND_ROBIN, SASL, SUBTREE, Connection,
                   Server, ServerPool, Tls)

from .models import ADUser


class ADConnection:
    """This class contains the functionality concerning the
    connection and the methods that gets data from AD and can modify the AD.
    """

    def __init__(self, servers: List, search_base: str, *args, **kwargs):
        self.connection = self._get_ad_connection(servers, *args, **kwargs)
        self.search_base = search_base

    def _get_ad_connection(self, servers: List, *args, **kwargs) -> Connection:
        """initializes a connection to the active directory.
        """

        tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        ldap_servers = [Server(x, use_ssl=True, tls=tls) for x in servers]
        server_pool = ServerPool(ldap_servers, ROUND_ROBIN, active=True, exhaust=True)
        connection = Connection(
            server_pool,
            authentication=SASL,
            sasl_mechanism=KERBEROS,
            receive_timeout=10,
            *args,
            **kwargs,
        )

        if connection.strategy_type == MOCK_SYNC or connection.bind():
            return connection
        return True

    def _get_paged_search(self, search_filter: str, attributes: List[str]):
        """Returns a entry_generator.
        """

        entry_generator = self.ad_connection.extend.standard.paged_search(
            search_base=self.search_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes,
            paged_size=100,
            generator=True,
        )
        return entry_generator

    def search(self, search_filter: str, attributes: List[str] = None
               ) -> List[Dict[str, str]]:
        """Returns a single result or false if none exist.

        Args:
            search_filter (str): An LDAP filter string.
            attributes (List[str]): A list of attributes that will be fetched.
                default to a list of all attributes

        Returns:
            List[Dict[str, str]]: AD objects presented as dictionaries.
        """

        if attributes is None:
            attributes = ALL_ATTRIBUTES

        entry_generator = self._get_paged_search(search_filter, attributes)
        result_list = [x['attributes'] for x in entry_generator if 'attributes' in x]
        return [collections.defaultdict(lambda: '', x) for x in result_list]

    def get(self, search_filter: str, attributes: List[str] = None) -> Dict[str, str]:
        """Returns a single result, the first result if more then one result
        is matched and an empty dict if zero results where returned.

        Args:
            search_filter (str): An LDAP filter string.
            attributes (List[str]): A list of attributes that will be fetched.

        Returns:
            Dict[str, str]: AD object as a dict, empty values if none were found.
        """

        search_result = self.search(search_filter, attributes)
        if len(search_result) > 0:
            return search_result
        return collections.defaultdict(lambda: '')

    def get_users(self, search_filter: str = '(objectClass=user)',
                  attributes: List[str] = None) -> List[ADUser]:
        """Returns all users that are not students in Kopavogur.

        Args:
            attributes (List[str]): A list of attributes that will be fetched.

        Returns:
            List[ADUser]: The users as AD User objects in a list.
        """

        if attributes is None:
            attributes = ADUser.attributes()
        ad_users = self.search(search_filter, attributes)

        users = [from_dict(data_class=ADUser, data=x) for x in ad_users]
        return users

    def modify(self, distinguished_name: str, changes: Dict[str, str]
               ) -> Dict[str, Any]:
        """Takes in distinguished_name and dict of changes.

        Example:
            modify(user_distinguishedName, {'departmentNumber': '11122'})

        Args:
            distinguished_name (str): A distinguished name of a AD User.
            changes (Dict[str, str]): {'AD field name': 'new field value'}

        Returns:
            Dict[str, Any]: The result from the attempted modification
        """

        changes = {key: [MODIFY_REPLACE, value] for key, value in changes.items()}
        success = self.ad_connection.modify(distinguished_name, changes)
        return {'result': self.ad_connection.result, 'success': success}

    def add_value(self, distinguished_name: str, changes: Dict[str, str]
                  ) -> Dict[str, Any]:
        """Takes in distinguished_name and dict of field and value where the value is
        added to the field specified, this is very useful to add a value to a list.

        Example:
            modify(group_distinguishedName, {'member': 'user_distinguishedName'})

        Args:
            distinguished_name (str): A distinguished name of a AD Object.
            changes (Dict[str, str]): {'AD field name': 'value to be added'}

        Returns:
            Dict[str, Any]: The result from the attempted addition
        """

        changes = {key: [MODIFY_ADD, value] for key, value in changes.items()}
        success = self.ad_connection.modify(distinguished_name, changes)
        return {'result': self.ad_connection.result, 'success': success}

    def remove_value(self, distinguished_name: str, changes: Dict[str, str]
                     ) -> Dict[str, Any]:
        """Takes in distinguished_name and dict of field and value where the specified
        value is removed to the field specified, this is very useful to add a value to
        a list.

        Example:
            modify(group_distinguishedName, {'member': 'user_distinguishedName'})

        Args:
            distinguished_name (str): A distinguished name of a AD Object.
            changes (Dict[str, str]): {'AD field name': 'value to be deleted'}

        Returns:
            Dict[str, Any]: The result from the attempted addition
        """

        changes = {key: [MODIFY_DELETE, value] for key, value in changes.items()}
        success = self.ad_connection.modify(distinguished_name, changes)
        return {'result': self.ad_connection.result, 'success': success}

    def add_member(self, user, group):
        """Takes in a user object and a group object adds the specified user
        to the group in AD.

        Args:
            user (ADUser): AD user object
            group (ADGroup): AD group object

        Returns:
            str: The result from the attempt to add the user to the group
        """

        changes = {'member': user.dn}
        return self.add_value(group.dn, changes)

    def remove_member(self, user, group):
        """Takes in a user object and a group object removes the specified user
        from the group in AD.

        Args:
            user (ADUser): AD user object
            group (ADGroup): AD group object

        Returns:
            str: The result from the attempt to remove the user from the group
        """

        changes = {'member': user.dn}
        return self.remove_value(group.dn, changes)
