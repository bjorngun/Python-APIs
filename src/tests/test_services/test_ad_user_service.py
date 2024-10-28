# File: src/tests/services/test_ad_user_service.py

import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import json
import os

# Adjust the import based on your project structure
from services import ADUserService
from models.ad_user import ADUser

class TestADUserService(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.patcher_getenv = patch('os.getenv')
        self.mock_getenv = self.patcher_getenv.start()
        self.addCleanup(self.patcher_getenv.stop)

        # Set up environment variables
        self.mock_getenv.side_effect = lambda key: {
            'ADUSER_DB_SERVER': 'test_server',
            'ADUSER_DB_NAME': 'test_db',
            'ADUSER_SQL_DRIVER': 'test_driver',
            'LDAP_SERVER_LIST': 'ldap://server1 ldap://server2',
            'SEARCH_BASE': 'dc=example,dc=com',
        }.get(key, None)

        # Mock ADConnection and SQLConnection classes
        self.patcher_ad_connection = patch('services.ad_user_service.ADConnection')
        self.mock_ad_connection_cls = self.patcher_ad_connection.start()
        self.addCleanup(self.patcher_ad_connection.stop)

        self.patcher_sql_connection = patch('services.ad_user_service.SQLConnection')
        self.mock_sql_connection_cls = self.patcher_sql_connection.start()
        self.addCleanup(self.patcher_sql_connection.stop)

        # Create mock instances
        self.mock_ad_connection = MagicMock()
        self.mock_ad_connection_cls.return_value = self.mock_ad_connection

        self.mock_sql_connection = MagicMock()
        self.mock_sql_connection_cls.return_value = self.mock_sql_connection

        # Reset cache attributes
        ADUserService._attributes_cache = None
        ADUserService._attributes_extended_cache = None

    def test_init_with_connections(self):
        # Pass mock connections to the service
        mock_ad_conn = MagicMock()
        mock_sql_conn = MagicMock()
        service = ADUserService(ad_connection=mock_ad_conn, sql_connection=mock_sql_conn)

        # Verify that _get_sql_connection and _get_ad_connection are not called
        self.mock_sql_connection_cls.assert_not_called()
        self.mock_ad_connection_cls.assert_not_called()

        # Verify that the connections are set correctly
        self.assertIs(service.sql_connection, mock_sql_conn)
        self.assertIs(service.ad_connection, mock_ad_conn)

    def test_get_users(self):
        # Initialize the service
        service = ADUserService()

        # Mock the SQL session query
        mock_query = MagicMock()
        self.mock_sql_connection.session.query.return_value = mock_query
        mock_query.all.return_value = ['user1', 'user2']

        # Call get_users
        users = service.get_users()

        # Verify that the query is made
        self.mock_sql_connection.session.query.assert_called_once_with(ADUser)
        mock_query.all.assert_called_once()

        # Verify the result
        self.assertEqual(users, ['user1', 'user2'])

    def test_add_member(self):
        # Initialize the service
        service = ADUserService()

        # Create a mock user
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'user_dn'
        group_dn = 'group_dn'

        # Mock the ad_connection.add_member method
        self.mock_ad_connection.add_member.return_value = {'result': 'success'}

        # Call add_member
        result = service.add_member(user, group_dn)

        # Verify that add_member is called with correct arguments
        self.mock_ad_connection.add_member.assert_called_once_with('user_dn', group_dn)

        # Verify the result
        self.assertEqual(result, {'result': 'success'})

    def test_remove_member(self):
        # Initialize the service
        service = ADUserService()

        # Create a mock user
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'user_dn'
        group_dn = 'group_dn'

        # Mock the ad_connection.remove_member method
        self.mock_ad_connection.remove_member.return_value = {'result': 'success'}

        # Call remove_member
        result = service.remove_member(user, group_dn)

        # Verify that remove_member is called with correct arguments
        self.mock_ad_connection.remove_member.assert_called_once_with('user_dn', group_dn)

        # Verify the result
        self.assertEqual(result, {'result': 'success'})

    def test_modify(self):
        # Initialize the service
        service = ADUserService()

        # Create a mock user
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'user_dn'
        changes = [('field1', 'value1'), ('field2', 'value2')]

        # Mock the ad_connection.modify method
        self.mock_ad_connection.modify.return_value = {'result': 'success'}

        # Call modify
        result = service.modify(user, changes)

        # Verify that modify is called with correct arguments
        self.mock_ad_connection.modify.assert_called_once_with('user_dn', changes)

        # Verify the result
        self.assertEqual(result, {'result': 'success'})

    def test_attributes_standard(self):
        # Mock os.path and open
        with patch('os.path.dirname') as mock_dirname, \
             patch('os.path.abspath') as mock_abspath, \
             patch('os.path.join') as mock_join, \
             patch('builtins.open', mock_open(read_data='["attr1", "attr2"]')), \
             patch('json.load') as mock_json_load:

            mock_dirname.return_value = '/path/to/dir'
            mock_abspath.return_value = '/path/to/dir'
            mock_join.return_value = '/path/to/dir/ad_user_attributes.json'
            mock_json_load.return_value = ["attr1", "attr2"]

            # Call attributes
            attrs = ADUserService.attributes()

            # Verify that json.load is called
            mock_json_load.assert_called_once()

            # Verify the result
            self.assertEqual(attrs, ["attr1", "attr2"])

    def test_attributes_extended(self):
        # Mock os.path and open
        with patch('os.path.dirname') as mock_dirname, \
             patch('os.path.abspath') as mock_abspath, \
             patch('os.path.join') as mock_join, \
             patch('builtins.open', mock_open(read_data='["ext_attr1", "ext_attr2"]')), \
             patch('json.load') as mock_json_load:

            mock_dirname.return_value = '/path/to/dir'
            mock_abspath.return_value = '/path/to/dir'
            mock_join.return_value = '/path/to/dir/ad_user_attributes_extended.json'
            mock_json_load.return_value = ["ext_attr1", "ext_attr2"]

            # Call attributes with extended=True
            attrs = ADUserService.attributes(extended=True)

            # Verify that json.load is called
            mock_json_load.assert_called_once()

            # Verify the result
            self.assertEqual(attrs, ["ext_attr1", "ext_attr2"])

    def test_load_attributes_file_not_found(self):
        # Mock os.path and open to raise FileNotFoundError
        with patch('os.path.dirname') as mock_dirname, \
             patch('os.path.abspath') as mock_abspath, \
             patch('os.path.join') as mock_join, \
             patch('builtins.open', side_effect=FileNotFoundError):

            mock_dirname.return_value = '/path/to/dir'
            mock_abspath.return_value = '/path/to/dir'
            mock_join.return_value = '/path/to/dir/non_existent_file.json'

            # Expect FileNotFoundError
            with self.assertRaises(FileNotFoundError):
                ADUserService._load_attributes('non_existent_file.json', '_attributes_cache')

    def test_load_attributes_json_decode_error(self):
        # Mock os.path and open to raise JSONDecodeError
        with patch('os.path.dirname') as mock_dirname, \
             patch('os.path.abspath') as mock_abspath, \
             patch('os.path.join') as mock_join, \
             patch('builtins.open', mock_open(read_data='invalid json')), \
             patch('json.load', side_effect=json.JSONDecodeError('Expecting value', 'invalid json', 0)):

            mock_dirname.return_value = '/path/to/dir'
            mock_abspath.return_value = '/path/to/dir'
            mock_join.return_value = '/path/to/dir/invalid.json'

            # Expect ValueError
            with self.assertRaises(ValueError):
                ADUserService._load_attributes('invalid.json', '_attributes_cache')

if __name__ == '__main__':
    unittest.main()
