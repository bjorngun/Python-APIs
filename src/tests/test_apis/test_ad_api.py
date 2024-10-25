import unittest
from unittest.mock import patch, MagicMock
import collections
import ssl

from ldap3 import MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, ALL_ATTRIBUTES, SUBTREE
from apis.ad_api import ADConnection

class TestADConnection(unittest.TestCase):
    def setUp(self):
        # Mock the Connection class to avoid real LDAP connections
        patcher = patch('apis.ad_api.Connection')
        self.addCleanup(patcher.stop)
        self.mock_connection_cls = patcher.start()
        self.mock_connection = MagicMock()
        self.mock_connection_cls.return_value = self.mock_connection
        self.mock_connection.bind.return_value = True


    @patch('apis.ad_api.ServerPool')
    @patch('apis.ad_api.Server')
    @patch('apis.ad_api.Connection')
    @patch('apis.ad_api.Tls')
    def test_get_ad_connection(self, mock_tls, mock_connection_cls, mock_server_cls, mock_server_pool):
        # Arrange
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        mock_tls_obj = MagicMock()
        mock_tls.return_value = mock_tls_obj
        mock_server_obj = MagicMock()
        mock_server_cls.return_value = mock_server_obj
        mock_server_pool_obj = MagicMock()
        mock_server_pool.return_value = mock_server_pool_obj
        mock_connection = MagicMock()
        mock_connection.bind.return_value = True
        mock_connection_cls.return_value = mock_connection

        # Mock _get_ad_connection during initialization
        with patch('apis.ad_api.ADConnection._get_ad_connection') as mock_get_ad_connection:
            mock_get_ad_connection.return_value = mock_connection
            ad_conn = ADConnection(servers, search_base)

        # Reset mocks to clear any calls made during initialization
        mock_tls.reset_mock()
        mock_connection_cls.reset_mock()
        mock_server_cls.reset_mock()
        mock_server_pool.reset_mock()

        # Act
        connection = ad_conn._get_ad_connection(servers)

        # Assert
        mock_tls.assert_called_once_with(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        self.assertEqual(mock_server_cls.call_count, len(servers))
        mock_server_pool.assert_called_once_with(
            [mock_server_obj, mock_server_obj], 'ROUND_ROBIN', active=True, exhaust=True
        )
        mock_connection_cls.assert_called_once_with(
            mock_server_pool_obj,
            authentication='SASL',
            sasl_mechanism='GSSAPI',
            receive_timeout=10,
        )
        mock_connection.bind.assert_called_once()
        self.assertEqual(connection, mock_connection)

    @patch('apis.ad_api.ADConnection._get_paged_search')
    def test_search(self, mock_get_paged_search):
        # Initialize ADConnection here
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        self.ad_conn = ADConnection(servers, search_base)

        # Arrange
        search_filter = '(objectClass=user)'
        attributes = ['cn', 'mail']
        mock_entry = {'attributes': {'cn': 'John Doe', 'mail': 'john@example.com'}}
        mock_get_paged_search.return_value = [mock_entry]

        # Act
        result = self.ad_conn.search(search_filter, attributes)

        # Assert
        expected_result = [{'cn': 'John Doe', 'mail': 'john@example.com'}]
        self.assertEqual(result, expected_result)
        mock_get_paged_search.assert_called_once_with(search_filter, attributes)

    def test_modify(self):
        # Initialize ADConnection here
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        self.ad_conn = ADConnection(servers, search_base)

        # Arrange
        distinguished_name = 'cn=John Doe,ou=users,dc=example,dc=com'
        changes = {'departmentNumber': '11122'}
        expected_changes = {'departmentNumber': [MODIFY_REPLACE, '11122']}
        self.mock_connection.modify.return_value = True
        self.mock_connection.result = {'description': 'success'}

        # Act
        result = self.ad_conn.modify(distinguished_name, changes)

        # Assert
        self.mock_connection.modify.assert_called_once_with(distinguished_name, expected_changes)
        expected_result = {'result': {'description': 'success'}, 'success': True}
        self.assertEqual(result, expected_result)

    def test_add_value(self):
        # Initialize ADConnection here
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        self.ad_conn = ADConnection(servers, search_base)

        # Arrange
        distinguished_name = 'cn=Group,ou=groups,dc=example,dc=com'
        changes = {'member': 'cn=John Doe,ou=users,dc=example,dc=com'}
        expected_changes = {'member': [MODIFY_ADD, 'cn=John Doe,ou=users,dc=example,dc=com']}
        self.mock_connection.modify.return_value = True
        self.mock_connection.result = {'description': 'success'}

        # Act
        result = self.ad_conn.add_value(distinguished_name, changes)

        # Assert
        self.mock_connection.modify.assert_called_once_with(distinguished_name, expected_changes)
        expected_result = {'result': {'description': 'success'}, 'success': True}
        self.assertEqual(result, expected_result)

    def test_remove_value(self):
        # Initialize ADConnection here
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        self.ad_conn = ADConnection(servers, search_base)

        # Arrange
        distinguished_name = 'cn=Group,ou=groups,dc=example,dc=com'
        changes = {'member': 'cn=John Doe,ou=users,dc=example,dc=com'}
        expected_changes = {'member': [MODIFY_DELETE, 'cn=John Doe,ou=users,dc=example,dc=com']}
        self.mock_connection.modify.return_value = True
        self.mock_connection.result = {'description': 'success'}

        # Act
        result = self.ad_conn.remove_value(distinguished_name, changes)

        # Assert
        self.mock_connection.modify.assert_called_once_with(distinguished_name, expected_changes)
        expected_result = {'result': {'description': 'success'}, 'success': True}
        self.assertEqual(result, expected_result)

    @patch('apis.ad_api.ADConnection.add_value')
    def test_add_member(self, mock_add_value):
        # Initialize ADConnection here
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        self.ad_conn = ADConnection(servers, search_base)

        # Arrange
        user_dn = 'cn=John Doe,ou=users,dc=example,dc=com'
        group_dn = 'cn=Admins,ou=groups,dc=example,dc=com'
        mock_add_value.return_value = {'result': {'description': 'success'}, 'success': True}

        # Act
        result = self.ad_conn.add_member(user_dn, group_dn)

        # Assert
        mock_add_value.assert_called_once_with(group_dn, {'member': user_dn})
        self.assertEqual(result, {'result': {'description': 'success'}, 'success': True})

    @patch('apis.ad_api.ADConnection.remove_value')
    def test_remove_member(self, mock_remove_value):
        # Initialize ADConnection here
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        self.ad_conn = ADConnection(servers, search_base)

        # Arrange
        user_dn = 'cn=John Doe,ou=users,dc=example,dc=com'
        group_dn = 'cn=Admins,ou=groups,dc=example,dc=com'
        mock_remove_value.return_value = {'result': {'description': 'success'}, 'success': True}

        # Act
        result = self.ad_conn.remove_member(user_dn, group_dn)

        # Assert
        mock_remove_value.assert_called_once_with(group_dn, {'member': user_dn})
        self.assertEqual(result, {'result': {'description': 'success'}, 'success': True})

    def test_get_paged_search(self):
        # Initialize ADConnection here
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        self.ad_conn = ADConnection(servers, search_base)

        # Arrange
        search_filter = '(objectClass=user)'
        attributes = ['cn', 'mail']
        self.mock_connection.extend.standard.paged_search.return_value = iter([
            {'attributes': {'cn': 'John Doe', 'mail': 'john@example.com'}}
        ])

        # Act
        result = self.ad_conn._get_paged_search(search_filter, attributes)

        # Assert
        self.mock_connection.extend.standard.paged_search.assert_called_once_with(
            search_base='dc=example,dc=com',
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=attributes,
            paged_size=100,
            generator=True,
        )
        self.assertTrue(hasattr(result, '__iter__'))

    def test_get_paged_search_no_attributes(self):
        # Initialize ADConnection here
        servers = ['ldap://server1', 'ldap://server2']
        search_base = 'dc=example,dc=com'
        self.ad_conn = ADConnection(servers, search_base)

        # Arrange
        search_filter = '(objectClass=user)'
        self.mock_connection.extend.standard.paged_search.return_value = iter([])

        # Act
        result = self.ad_conn._get_paged_search(search_filter, ALL_ATTRIBUTES)

        # Assert
        self.mock_connection.extend.standard.paged_search.assert_called_once_with(
            search_base='dc=example,dc=com',
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=ALL_ATTRIBUTES,
            paged_size=100,
            generator=True,
        )
        self.assertTrue(hasattr(result, '__iter__'))
