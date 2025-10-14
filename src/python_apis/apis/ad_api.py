"""This module contains the functionality concerning the
connection and the methods that gets data from AD and can modify the AD.

This module was build as an "in the same domain" AD connection and has no plans
to extend to being able to connect through a custom user and password. Hence
this package will need a user that has the required permissions to edit/read the
AD to run it effectively.
"""

import collections
import ssl
from typing import Any

from ldap3.utils.log import set_library_log_detail_level, BASIC
from ldap3 import (ALL_ATTRIBUTES, MODIFY_ADD, MODIFY_DELETE,
                   MODIFY_REPLACE, ROUND_ROBIN, SASL, SUBTREE, GSSAPI,
                   Connection, Server, ServerPool, Tls)


class ADConnectionError(Exception):
    """Custom exception for errors related to Active Directory connections."""


class ADMissingServersError(Exception):
    """Custom exception for errors related to missing Active Directory servers."""


class ADConnection:
    """This class contains the functionality concerning the
    connection and the methods that gets data from AD and can modify the AD.
    """

    def __init__(self, servers: list, search_base: str, enable_ldap_logging: bool = False):
        if enable_ldap_logging:
            set_library_log_detail_level(BASIC)

        self.ad_connection = self._get_ad_connection(servers)
        self.search_base = search_base

    def _get_ad_connection(self, servers: list) -> Connection | None:
        """initializes a connection to the active directory.
        """
        if not servers:
            raise ADMissingServersError  # Explicitly handle empty server list

        tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        ldap_servers = [Server(x, use_ssl=True, tls=tls) for x in servers]

        server_pool = ServerPool(ldap_servers, ROUND_ROBIN, active=True, exhaust=True)

        connection = Connection(
            server_pool,
            authentication=SASL,
            sasl_mechanism=GSSAPI,
            receive_timeout=10,
        )
        if not connection.bind():
            raise ADConnectionError(
                f"Failed to bind to Active Directory: {connection.result['description']}"
            )
        return connection

    def _get_paged_search(self, search_filter: str, attributes: list[str]):
        """Returns a entry_generator.
        """
        entry_generator = self.ad_connection.extend.standard.paged_search(
            search_base=self.search_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes,
            paged_size=500,
            generator=True,
        )
        return entry_generator

    def search(
        self, search_filter: str, attributes: list[str] | None = None
    ) -> list[dict[str, str]]:
        """Returns a single result or false if none exist.

        Args:
            search_filter (str): An LDAP filter string.
            attributes (list[str]): A list of attributes that will be fetched.

        Returns:
            list[dict[str, str]]: AD objects presented as dictionaries.
        """

        if attributes is None:
            attributes = ALL_ATTRIBUTES

        entry_generator = self._get_paged_search(search_filter, attributes)
        result_list = [x['attributes'] for x in entry_generator if 'attributes' in x]
        for ad_object in result_list:
            self.set_ou_for_object(ad_object)
        return result_list

    def get(self, search_filter: str, attributes: list[str] = None) -> dict[str, str]:
        """Returns a single result, the first result if more then one result
        is matched and an empty dict if zero results where returned.

        Args:
            search_filter (str): An LDAP filter string.
            attributes (list[str]): A list of attributes that will be fetched.

        Returns:
            dict[str, str]: AD object as a dict, empty values if none were found.
        """

        search_result = self.search(search_filter, attributes)
        return search_result[0] if len(search_result) > 0 else collections.defaultdict(lambda: '')

    def modify(self, distinguished_name: str, changes: list[tuple[str, str]]) -> dict[str, Any]:
        """Takes in distinguished_name and dict of changes.

        Example:
            modify(user_distinguishedName, [('departmentNumber': '11122')])

        Args:
            distinguished_name (str): A distinguished name of a AD User.
            changes (list[tuple[str, str]]): [('AD field name': 'new field value')]

        Returns:
            dict[str, Any]: The result from the attempted modification
        """

        changes = {key: [MODIFY_REPLACE, value] for key, value in changes}
        success = self.ad_connection.modify(distinguished_name, changes)
        return {'result': self.ad_connection.result, 'success': success}

    def add_value(self, distinguished_name: str, changes: dict[str, str]) -> dict[str, Any]:
        """Takes in distinguished_name and dict of field and value where the value is added to
        the field specified, this is very useful to add a value to a list.

        Example:
            modify(group_distinguishedName, {'member': 'user_distinguishedName'})

        Args:
            distinguished_name (str): A distinguished name of a AD Object.
            changes (dict[str, str]): {'AD field name': 'value to be added'}

        Returns:
            dict[str, Any]: The result from the attempted addition
        """

        changes = {key: [MODIFY_ADD, value] for key, value in changes.items()}
        success = self.ad_connection.modify(distinguished_name, changes)
        return {'result': self.ad_connection.result, 'success': success}

    def remove_value(self, distinguished_name: str, changes: dict[str, str]) -> dict[str, Any]:
        """Takes in distinguished_name and dict of field and value where the specified value is
        removed to the field specified, this is very useful to add a value to a
        list.

        Example:
            modify(group_distinguishedName, {'member': 'user_distinguishedName'})

        Args:
            distinguished_name (str): A distinguished name of a AD Object.
            changes (dict[str, str]): {'AD field name': 'value to be deleted'}

        Returns:
            dict[str, Any]: The result from the attempted addition
        """

        changes = {key: [MODIFY_DELETE, value] for key, value in changes.items()}
        success = self.ad_connection.modify(distinguished_name, changes)
        return {'result': self.ad_connection.result, 'success': success}

    def add_member(self, user_dn: str, group_dn: str):
        """Takes in a user distinguishedName and a group distinguishedName adds the specified user
        to the group in AD.

        Args:
            user_dn (str): AD user distinguishedName
            group_dn (str): AD group distinguishedName

        Returns:
            str: The result from the attempt to add the user to the group
        """

        changes = {'member': user_dn}
        return self.add_value(group_dn, changes)

    def remove_member(self, user_dn: str, group_dn: str):
        """Takes in a user distinguishedName and a group distinguishedName removes the specified
        user from the group in AD.

        Args:
            user_dn (str): AD user distinguishedName
            group_dn (str): AD group distinguishedName

        Returns:
            str: The result from the attempt to remove the user from the group
        """

        changes = {'member': user_dn}
        return self.remove_value(group_dn, changes)

    def move_entry(self, distinguished_name: str, new_ou_dn: str) -> dict[str, Any]:
        """Move an AD object to the provided OU while keeping the same relative DN.

        Args:
            distinguished_name (str): Current distinguished name for the AD object.
            new_ou_dn (str): Target OU distinguished name to move the object under.

        Returns:
            dict[str, Any]: Result payload containing the LDAP response and success flag.
        """

        relative_dn = distinguished_name.split(',', 1)[0]
        success = self.ad_connection.modify_dn(
            distinguished_name,
            relative_dn,
            new_superior=new_ou_dn,
        )
        return {'result': self.ad_connection.result, 'success': success}

    def set_ou_for_object(self, ad_object: dict[str, Any]) -> None:
        """Add the OU extracted from ``distinguishedName`` to ``ad_object``.

        This helper modifies ``ad_object`` in place if the object does not
        already contain the ``ou`` key.
        """

        if 'distinguishedName' in ad_object and 'ou' not in ad_object:
            if ',' not in ad_object['distinguishedName']:
                return
            ou = ','.join(ad_object['distinguishedName'].split(',')[1:])
            ad_object['ou'] = ou

    # ---------------------------------------------------------------------
    # Create new user
    # ---------------------------------------------------------------------
    def add_entry(self, distinguished_name: str, attributes: dict[str, object]) -> dict[str, Any]:
        """Create a new AD object (e.g., user) at the given DN with the provided attributes.
        `attributes` MUST include a valid objectClass list,
        e.g., ['top', 'person', 'organizationalPerson', 'user'].
        """

        success = self.ad_connection.add(distinguished_name, attributes=attributes)
        return {'result': self.ad_connection.result, 'success': success}

    def set_password(self, distinguished_name: str, new_password: str) -> dict[str, Any]:
        """Set the user's password. Requires LDAPS/StartTLS and appropriate rights.
        """

        password_ext = self.ad_connection.extend.microsoft
        success = password_ext.modify_password(distinguished_name, new_password)
        return {'result': self.ad_connection.result, 'success': success}

    def enable_user(self, distinguished_name: str) -> dict[str, Any]:
        """Enable an AD user by setting userAccountControl to 512 (NORMAL_ACCOUNT).
        """

        changes = {'userAccountControl': [MODIFY_REPLACE, 512]}
        success = self.ad_connection.modify(distinguished_name, changes)
        return {'result': self.ad_connection.result, 'success': success}
