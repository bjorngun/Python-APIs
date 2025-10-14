# test_ad_user_service.py

import unittest
from unittest.mock import patch, MagicMock, mock_open
from python_apis.services.ad_user_service import ADUserService
from python_apis.models.ad_user import ADUser
from python_apis.schemas.ad_user_schema import ADUserSchema
from pydantic import ValidationError


class TestADUserService(unittest.TestCase):

    def setUp(self):
        env_vars = {
            'ADUSER_DB_SERVER': 'test_server',
            'ADUSER_DB_NAME': 'test_db',
            'ADUSER_SQL_DRIVER': 'test_driver',
            'LDAP_SERVER_LIST': 'ldap://server1 ldap://server2',
            'SEARCH_BASE': 'dc=example,dc=com',
        }
        patcher_getenv = patch('os.getenv', side_effect=lambda k, d=None: env_vars.get(k, d))
        self.mock_getenv = patcher_getenv.start()
        self.addCleanup(patcher_getenv.stop)

        self.mock_ad_connection = MagicMock()
        self.mock_sql_connection = MagicMock()

        patcher_ad_connection = patch('python_apis.services.ad_user_service.ADConnection', return_value=self.mock_ad_connection)
        patcher_sql_connection = patch('python_apis.services.ad_user_service.SQLConnection', return_value=self.mock_sql_connection)

        self.mock_ad_connection_cls = patcher_ad_connection.start()
        self.mock_sql_connection_cls = patcher_sql_connection.start()

        self.addCleanup(patcher_ad_connection.stop)
        self.addCleanup(patcher_sql_connection.stop)

    def test_init_with_connections(self):
        ad_conn = MagicMock()
        sql_conn = MagicMock()
        service = ADUserService(ad_connection=ad_conn, sql_connection=sql_conn)

        self.assertIs(service.ad_connection, ad_conn)
        self.assertIs(service.sql_connection, sql_conn)

    @patch('python_apis.services.ad_user_service.ADUser.get_attribute_list', return_value=['attr1', 'attr2'])
    @patch('python_apis.services.ad_user_service.ADUserSchema')
    def test_get_users_from_ad(self, mock_ad_user_schema, mock_get_attr_list):
        service = ADUserService()

        ad_user_data = [
            {'sAMAccountName': 'user1', 'distinguishedName': 'dn1'},
            {'sAMAccountName': 'user2', 'distinguishedName': 'dn2'}
        ]
        self.mock_ad_connection.search.return_value = ad_user_data
        mock_ad_user_schema.side_effect = lambda **data: MagicMock(model_dump=lambda: data)

        users = service.get_users_from_ad()

        self.mock_ad_connection.search.assert_called_once_with('(objectClass=user)', ['attr1', 'attr2'])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0].sAMAccountName, 'user1')

    def test_add_member(self):
        service = ADUserService()
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'user_dn'
        self.mock_ad_connection.add_member.return_value = {'result': 'success'}

        result = service.add_member(user, 'group_dn')

        self.mock_ad_connection.add_member.assert_called_once_with('user_dn', 'group_dn')
        self.assertEqual(result, {'result': 'success'})

    def test_remove_member(self):
        service = ADUserService()
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'user_dn'
        self.mock_ad_connection.remove_member.return_value = {'result': 'success'}

        result = service.remove_member(user, 'group_dn')

        self.mock_ad_connection.remove_member.assert_called_once_with('user_dn', 'group_dn')
        self.assertEqual(result, {'result': 'success'})

    def test_move_user_to_ou_success(self):
        service = ADUserService()
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'CN=John Doe,OU=users,DC=example,DC=com'
        user.ou = 'OU=users,DC=example,DC=com'
        user.sAMAccountName = 'jdoe'
        target_ou_dn = 'OU=new,DC=example,DC=com'

        self.mock_ad_connection.move_entry.return_value = {'success': True, 'result': 'success'}

        result = service.move_user_to_ou(user, target_ou_dn)

        self.mock_ad_connection.move_entry.assert_called_once_with(
            'CN=John Doe,OU=users,DC=example,DC=com',
            target_ou_dn,
        )
        self.assertEqual(user.distinguishedName, 'CN=John Doe,OU=new,DC=example,DC=com')
        self.assertEqual(user.ou, target_ou_dn)
        self.assertEqual(result['dn'], 'CN=John Doe,OU=new,DC=example,DC=com')

    def test_move_user_to_ou_failure(self):
        service = ADUserService()
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'CN=John Doe,OU=users,DC=example,DC=com'
        user.ou = 'OU=users,DC=example,DC=com'
        user.sAMAccountName = 'jdoe'
        target_ou_dn = 'OU=new,DC=example,DC=com'

        self.mock_ad_connection.move_entry.return_value = {'success': False, 'result': 'error'}

        result = service.move_user_to_ou(user, target_ou_dn)

        self.mock_ad_connection.move_entry.assert_called_once_with(
            'CN=John Doe,OU=users,DC=example,DC=com',
            target_ou_dn,
        )
        self.assertEqual(user.distinguishedName, 'CN=John Doe,OU=users,DC=example,DC=com')
        self.assertEqual(user.ou, 'OU=users,DC=example,DC=com')
        self.assertEqual(result, {'success': False, 'result': 'error'})

    def test_modify_user(self):
        service = ADUserService()
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'user_dn'
        user.department = 'old'  # Explicitly set this attribute to a known value

        changes = [('department', 'HR')]

        self.mock_ad_connection.modify.return_value = {
            'result': 'success',
            'success': True,
            'changes': {'department': 'old -> HR'}
        }

        result = service.modify_user(user, changes)

        expected_result = {
            'result': 'success',
            'success': True,
            'changes': {'department': 'old -> HR'}
        }

        self.assertEqual(result, expected_result)



if __name__ == '__main__':
    unittest.main()
