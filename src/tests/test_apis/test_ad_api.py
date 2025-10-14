# test_ad_api.py
import unittest
from unittest.mock import patch, MagicMock
import ssl
from ldap3 import MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, ALL_ATTRIBUTES, SUBTREE, SASL, GSSAPI
from python_apis.apis.ad_api import ADConnection, ADConnectionError, ADMissingServersError


class TestADConnection(unittest.TestCase):

    def setUp(self):
        self.servers = ['ldap://server1', 'ldap://server2']
        self.search_base = 'dc=example,dc=com'

        patcher = patch('python_apis.apis.ad_api.Connection')
        self.mock_connection_cls = patcher.start()
        self.mock_connection = MagicMock()
        self.mock_connection.bind.return_value = True
        self.mock_connection_cls.return_value = self.mock_connection
        self.addCleanup(patcher.stop)

    def test_init_success(self):
        conn = ADConnection(self.servers, self.search_base)
        self.assertEqual(conn.search_base, self.search_base)
        self.assertIsNotNone(conn.ad_connection)

    def test_init_no_servers_raises_exception(self):
        with self.assertRaises(ADMissingServersError):
            ADConnection([], self.search_base)

    def test_init_bind_failure_raises_exception(self):
        self.mock_connection.bind.return_value = False
        self.mock_connection.result = {'description': 'Invalid credentials'}
        with self.assertRaises(ADConnectionError) as context:
            ADConnection(self.servers, self.search_base)

        self.assertIn('Failed to bind to Active Directory', str(context.exception))

    @patch('python_apis.apis.ad_api.ServerPool')
    @patch('python_apis.apis.ad_api.Server')
    def test_get_ad_connection(self, mock_server_cls, mock_server_pool_cls):
        mock_tls_obj = MagicMock()
        with patch('python_apis.apis.ad_api.Tls', return_value=mock_tls_obj) as mock_tls:
            ad_conn = ADConnection(self.servers, self.search_base)

        mock_tls.assert_called_once_with(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        self.assertEqual(mock_server_cls.call_count, len(self.servers))
        mock_server_pool_cls.assert_called_once()
        self.mock_connection.bind.assert_called_once()

    def test_search(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        mock_result = [{'attributes': {'cn': 'John Doe', 'mail': 'john@example.com'}}]
        self.mock_connection.extend.standard.paged_search.return_value = iter(mock_result)

        results = ad_conn.search('(objectClass=user)', ['cn', 'mail'])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['cn'], 'John Doe')
        self.mock_connection.extend.standard.paged_search.assert_called_once()

    def test_get_with_results(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        mock_result = [{'attributes': {'cn': 'John Doe'}}]
        self.mock_connection.extend.standard.paged_search.return_value = iter(mock_result)

        result = ad_conn.get('(objectClass=user)', ['cn'])

        self.assertEqual(result['cn'], 'John Doe')

    def test_get_no_results(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.return_value = iter([])

        result = ad_conn.get('(objectClass=user)', ['cn'])

        self.assertEqual(result['cn'], '')  # defaultdict returns empty string

    def test_modify(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        distinguished_name = 'cn=John Doe,ou=users,dc=example,dc=com'
        changes = [('department', 'IT')]
        self.mock_connection.modify.return_value = True
        self.mock_connection.result = {'description': 'success'}

        result = ad_conn.modify(distinguished_name, changes)

        expected_changes = {'department': [MODIFY_REPLACE, 'IT']}
        self.mock_connection.modify.assert_called_once_with(distinguished_name, expected_changes)
        self.assertTrue(result['success'])

    def test_add_value(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        distinguished_name = 'cn=Group,ou=groups,dc=example,dc=com'
        changes = {'member': 'cn=John Doe,ou=users,dc=example,dc=com'}

        self.mock_connection.modify.return_value = True
        result = ad_conn.add_value(distinguished_name, changes)

        expected_changes = {'member': [MODIFY_ADD, 'cn=John Doe,ou=users,dc=example,dc=com']}
        self.mock_connection.modify.assert_called_once_with(distinguished_name, expected_changes)
        self.assertTrue(result['success'])

    def test_remove_value(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        distinguished_name = 'cn=Group,ou=groups,dc=example,dc=com'
        changes = {'member': 'cn=John Doe,ou=users,dc=example,dc=com'}

        self.mock_connection.modify.return_value = True
        result = ad_conn.remove_value(distinguished_name, changes)

        expected_changes = {'member': [MODIFY_DELETE, 'cn=John Doe,ou=users,dc=example,dc=com']}
        self.mock_connection.modify.assert_called_once_with(distinguished_name, expected_changes)
        self.assertTrue(result['success'])

    def test_move_entry(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        distinguished_name = 'CN=John Doe,OU=users,DC=example,DC=com'
        new_ou_dn = 'OU=new,DC=example,DC=com'

        self.mock_connection.modify_dn.return_value = True
        self.mock_connection.result = {'description': 'success'}

        result = ad_conn.move_entry(distinguished_name, new_ou_dn)

        self.mock_connection.modify_dn.assert_called_once_with(
            distinguished_name,
            'CN=John Doe',
            new_superior=new_ou_dn,
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], {'description': 'success'})


if __name__ == '__main__':
    unittest.main()
