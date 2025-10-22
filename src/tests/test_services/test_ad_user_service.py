# test_ad_user_service.py

import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, mock_open
from ldap3.core.exceptions import LDAPException
from pydantic import ValidationError

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from python_apis.services.ad_user_service import ADUserService
from python_apis.models.ad_user import ADUser
from python_apis.schemas.ad_user_schema import ADUserSchema


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
        user = SimpleNamespace(
            distinguishedName='CN=John Doe,OU=users,DC=example,DC=com',
            ou='OU=users,DC=example,DC=com',
            sAMAccountName='jdoe',
            cn='John Doe',
        )
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
        user = SimpleNamespace(
            distinguishedName='CN=John Doe,OU=users,DC=example,DC=com',
            ou='OU=users,DC=example,DC=com',
            sAMAccountName='jdoe',
            cn='John Doe',
        )
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

    def test_set_password_success(self):
        service = ADUserService()
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'CN=John Doe,OU=users,DC=example,DC=com'
        user.sAMAccountName = 'jdoe'
        self.mock_ad_connection.set_password.return_value = {'success': True, 'result': 'ok'}

        result = service.set_password(user, 'Sup3rSecure!')

        self.mock_ad_connection.set_password.assert_called_once()
        call_args = self.mock_ad_connection.set_password.call_args
        self.assertEqual(
            call_args.args[:2],
            ('CN=John Doe,OU=users,DC=example,DC=com', 'Sup3rSecure!'),
        )
        self.assertEqual(result, {'success': True, 'result': 'ok'})

    def test_set_password_failure_response(self):
        service = ADUserService()
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'CN=Jane Doe,OU=users,DC=example,DC=com'
        user.sAMAccountName = 'jadoe'
        self.mock_ad_connection.set_password.return_value = {'success': False, 'result': 'error'}

        result = service.set_password(user, 'Temp1234!')

        self.assertEqual(result, {'success': False, 'result': 'error'})

    def test_set_password_exception(self):
        service = ADUserService()
        user = MagicMock(spec=ADUser)
        user.distinguishedName = 'CN=Jane Doe,OU=users,DC=example,DC=com'
        user.sAMAccountName = 'jadoe'
        self.mock_ad_connection.set_password.side_effect = LDAPException('boom')

        result = service.set_password(user, 'Temp1234!')

        self.assertEqual(result, {'success': False, 'result': 'boom'})

    def test_create_user_success_with_defaults(self):
        service = ADUserService()
        self.mock_ad_connection.add_entry.return_value = {'success': True, 'result': 'created'}

        result = service.create_user(
            'John Doe',
            'OU=Users,DC=example,DC=com',
            {'sAMAccountName': 'jdoe'},
        )

        self.assertEqual(
            self.mock_ad_connection.add_entry.call_args[0][0],
            'CN=John Doe,OU=Users,DC=example,DC=com',
        )
        passed_attrs = self.mock_ad_connection.add_entry.call_args[0][1]
        self.assertIn('objectClass', passed_attrs)
        self.assertIn('user', passed_attrs['objectClass'])
        self.assertEqual(
            result,
            {'success': True, 'result': 'created', 'dn': 'CN=John Doe,OU=Users,DC=example,DC=com'},
        )

    def test_create_user_add_entry_failure(self):
        service = ADUserService()
        self.mock_ad_connection.add_entry.return_value = {'success': False, 'result': 'error'}

        result = service.create_user(
            'Jane Doe',
            'OU=Users,DC=example,DC=com',
            {'sAMAccountName': 'jadoe'},
        )

        self.assertEqual(
            result,
            {'success': False, 'result': 'error', 'dn': 'CN=Jane Doe,OU=Users,DC=example,DC=com'},
        )

    def test_create_user_password_failure(self):
        service = ADUserService()
        self.mock_ad_connection.add_entry.return_value = {'success': True, 'result': 'created'}
        self.mock_ad_connection.set_password.return_value = {'success': False, 'result': 'pw err'}

        result = service.create_user(
            'John Doe',
            'OU=Users,DC=example,DC=com',
            {'sAMAccountName': 'jdoe'},
            set_password='Sup3rSecure!',
        )

        self.assertEqual(
            result,
            {
                'success': False,
                'result': {'create': 'created', 'password': 'pw err'},
                'dn': 'CN=John Doe,OU=Users,DC=example,DC=com',
            },
        )

    def test_create_user_enable_failure(self):
        service = ADUserService()
        self.mock_ad_connection.add_entry.return_value = {'success': True, 'result': 'created'}
        self.mock_ad_connection.enable_user.return_value = {
            'success': False,
            'result': 'enable err',
        }

        result = service.create_user(
            'John Doe',
            'OU=Users,DC=example,DC=com',
            {'sAMAccountName': 'jdoe'},
            enable_after_create=True,
        )

        self.assertEqual(
            result,
            {
                'success': False,
                'result': {'create': 'created', 'enable': 'enable err'},
                'dn': 'CN=John Doe,OU=Users,DC=example,DC=com',
            },
        )

    def test_create_user_unexpected_option(self):
        service = ADUserService()

        with self.assertRaises(ValueError):
            service.create_user(
                'John Doe',
                'OU=Users,DC=example,DC=com',
                {'sAMAccountName': 'jdoe'},
                unexpected=True,
            )

    def test_create_user_add_entry_exception(self):
        service = ADUserService()
        self.mock_ad_connection.add_entry.side_effect = LDAPException('nope')

        result = service.create_user(
            'John Doe',
            'OU=Users,DC=example,DC=com',
            {'sAMAccountName': 'jdoe'},
        )

        self.assertEqual(
            result,
            {'success': False, 'result': 'nope', 'dn': 'CN=John Doe,OU=Users,DC=example,DC=com'},
        )



if __name__ == '__main__':
    unittest.main()
