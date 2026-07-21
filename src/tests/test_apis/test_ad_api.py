# test_ad_api.py
import unittest
from unittest.mock import ANY, call, patch, MagicMock
import ssl
from ldap3 import (
    BASE,
    GSSAPI,
    LEVEL,
    MODIFY_ADD,
    MODIFY_DELETE,
    MODIFY_REPLACE,
    SASL,
    SIMPLE,
    SUBTREE,
)
from ldap3.core.exceptions import (
    LDAPCommunicationError,
    LDAPInvalidFilterError,
    LDAPResponseTimeoutError,
    LDAPSessionTerminatedByServerError,
)
from python_apis.apis.ad_api import (
    ADBindError,
    ADConnection,
    ADConnectionError,
    ADMissingServersError,
)
from python_apis.apis.ad_config import ADTLSConfig
from python_apis.apis.ad_errors import (
    ADMalformedQueryError,
    ADMalformedResultError,
    ADQueryRejectedError,
    ADTimeoutError,
    ADTransportError,
)
from python_apis.services.error_taxonomy import AD_PERMISSION_DENIED


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
        self.assertIsNotNone(conn.connection)

    def test_init_accepts_legacy_positional_logging_argument(self):
        conn = ADConnection(self.servers, self.search_base, False)

        self.assertEqual(conn.search_base, self.search_base)
        self.assertIsNotNone(conn.connection)

    def test_invalid_authentication_fails_before_ldap_construction(self):
        invalid_options = (
            {"authentication": "unknown"},
            {"authentication": "gssapi", "username": "USER_CANARY"},
            {"authentication": "gssapi", "password": "PASSWORD_CANARY"},
            {"authentication": "simple", "username": "", "password": "secret"},
            {"authentication": "simple", "username": "user", "password": ""},
            {"authentication": "simple", "username": "user", "password": "secret"},
            {
                "authentication": "simple",
                "username": "user",
                "password": "secret",
                "tls": ADTLSConfig(validate=ssl.CERT_NONE),
            },
        )

        for options in invalid_options:
            with self.subTest(options=options), patch(
                'python_apis.apis.ad_api.Server'
            ) as mock_server_cls, self.assertRaises(ValueError):
                ADConnection(self.servers, self.search_base, **options)

            mock_server_cls.assert_not_called()
            self.mock_connection_cls.assert_not_called()

    def test_simple_bind_uses_credentials_and_scrubs_bound_connection(self):
        username = 'SIMPLE_USER_CANARY'
        password = 'SIMPLE_PASSWORD_CANARY'

        connection = ADConnection(
            self.servers,
            self.search_base,
            authentication='simple',
            username=username,
            password=password,
            tls=ADTLSConfig.secure(),
        )

        connection_options = self.mock_connection_cls.call_args.kwargs
        self.assertEqual(connection_options['authentication'], SIMPLE)
        self.assertEqual(connection_options['user'], username)
        self.assertEqual(connection_options['password'], password)
        self.assertFalse(connection_options['auto_referrals'])
        self.assertIsNone(self.mock_connection.user)
        self.assertIsNone(self.mock_connection.password)
        self.assertEqual(connection.authentication_mode, 'simple')
        self.assertNotIn(username, repr(connection))
        self.assertNotIn(password, repr(connection))
        self.assertNotIn(username, repr(connection.connection))
        self.assertNotIn(password, repr(connection.connection))

    def test_simple_bind_failure_uses_safe_error(self):
        self.mock_connection.bind.return_value = False
        self.mock_connection.result = {
            'result': 49,
            'description': 'PASSWORD_CANARY_INVALID',
        }
        self.mock_connection.server.host = 'RAW_SERVER_CANARY'

        with self.assertRaises(ADBindError) as captured_error:
            ADConnection(
                self.servers,
                self.search_base,
                authentication='simple',
                username='SIMPLE_USER_CANARY',
                password='SIMPLE_PASSWORD_CANARY',
                tls=ADTLSConfig.secure(),
            )

        message = str(captured_error.exception)
        self.assertNotIn('SIMPLE_USER_CANARY', message)
        self.assertNotIn('SIMPLE_PASSWORD_CANARY', message)
        self.assertNotIn('PASSWORD_CANARY_INVALID', message)
        self.assertNotIn('RAW_SERVER_CANARY', message)

    def test_simple_bind_rebind_reuses_private_credentials(self):
        connection = ADConnection(
            self.servers,
            self.search_base,
            authentication='simple',
            username='SIMPLE_USER_CANARY',
            password='SIMPLE_PASSWORD_CANARY',
            tls=ADTLSConfig.secure(),
        )
        self.mock_connection_cls.reset_mock()

        connection.rebind()

        connection_options = self.mock_connection_cls.call_args.kwargs
        self.assertEqual(connection_options['user'], 'SIMPLE_USER_CANARY')
        self.assertEqual(connection_options['password'], 'SIMPLE_PASSWORD_CANARY')
        self.assertIsNone(connection.connection.user)
        self.assertIsNone(connection.connection.password)

    @patch('python_apis.apis.ad_api.set_library_log_detail_level')
    @patch('python_apis.apis.ad_api.set_library_log_hide_sensitive_data')
    def test_opt_in_ldap_logging_forces_sensitive_data_hiding(
        self, mock_hide_sensitive, mock_detail_level
    ):
        ADConnection(self.servers, self.search_base, enable_ldap_logging=True)

        mock_hide_sensitive.assert_called_once_with(True)
        mock_detail_level.assert_called_once_with(ANY)

    def test_init_no_servers_raises_exception(self):
        with self.assertRaises(ADMissingServersError):
            ADConnection([], self.search_base)

    def test_init_bind_failure_raises_exception(self):
        self.mock_connection.bind.return_value = False
        self.mock_connection.result = {'result': 49, 'description': 'Invalid credentials'}
        self.mock_connection.server.host = 'server1'
        with self.assertRaises(ADBindError) as context:
            ADConnection(self.servers, self.search_base)

        self.assertIn('Failed to bind to Active Directory', str(context.exception))
        self.assertEqual(context.exception.result_code, 49)
        self.assertTrue(context.exception.controller.startswith('controller-'))
        self.assertNotIn('server1', str(context.exception))
        self.assertNotIn('Invalid credentials', str(context.exception))

    def test_init_bind_exception_is_chained_to_safe_bind_error(self):
        original_error = LDAPCommunicationError('raw controller detail')
        self.mock_connection.bind.side_effect = original_error
        self.mock_connection.server.host = 'server1'

        with self.assertRaises(ADBindError) as context:
            ADConnection(self.servers, self.search_base)

        self.assertIs(context.exception.__cause__, original_error)
        self.assertNotIn('raw controller detail', str(context.exception))

    @patch('python_apis.apis.ad_api.ServerPool')
    @patch('python_apis.apis.ad_api.Server')
    def test_get_ad_connection(self, mock_server_cls, mock_server_pool_cls):
        mock_tls_obj = MagicMock()
        with patch('python_apis.apis.ad_api.Tls', return_value=mock_tls_obj) as mock_tls:
            ADConnection(self.servers, self.search_base)

        mock_tls.assert_called_once_with(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        self.assertEqual(mock_server_cls.call_count, len(self.servers))
        mock_server_pool_cls.assert_called_once()
        connection_options = self.mock_connection_cls.call_args.kwargs
        self.assertEqual(connection_options['authentication'], SASL)
        self.assertEqual(connection_options['sasl_mechanism'], GSSAPI)
        self.assertNotIn('user', connection_options)
        self.assertNotIn('password', connection_options)
        self.mock_connection.bind.assert_called_once()

    @patch('python_apis.apis.ad_api.ServerPool')
    @patch('python_apis.apis.ad_api.Server')
    def test_secure_tls_is_per_server_and_validated(
        self, mock_server_cls, _mock_server_pool_cls
    ):
        tls_objects = [MagicMock(name='tls-server1'), MagicMock(name='tls-server2')]
        tls_config = ADTLSConfig.secure(
            ca_certs_data="TEST_CA_DATA",
            valid_names=("directory.example.test",),
        )

        with patch('python_apis.apis.ad_api.Tls', side_effect=tls_objects) as mock_tls, patch(
            'python_apis.apis.ad_api.ssl.create_default_context'
        ):
            connection = ADConnection(
                self.servers,
                self.search_base,
                connect_timeout=4,
                tls=tls_config,
            )

        self.assertIs(connection.tls_config, tls_config)
        self.assertEqual(mock_tls.call_count, 2)
        self.assertEqual(
            [tls_call.kwargs['sni'] for tls_call in mock_tls.call_args_list],
            ['server1', 'server2'],
        )
        for tls_call in mock_tls.call_args_list:
            self.assertEqual(tls_call.kwargs['validate'], ssl.CERT_REQUIRED)
            self.assertIsNone(tls_call.kwargs['version'])
            self.assertEqual(tls_call.kwargs['ca_certs_data'], "TEST_CA_DATA")
            self.assertEqual(
                tls_call.kwargs['valid_names'], ("directory.example.test",)
            )
        mock_server_cls.assert_has_calls([
            call('server1', use_ssl=True, tls=tls_objects[0], connect_timeout=4),
            call('server2', use_ssl=True, tls=tls_objects[1], connect_timeout=4),
        ])

    @patch('python_apis.apis.ad_api.ServerPool')
    @patch('python_apis.apis.ad_api.Server')
    def test_secure_tls_preserves_explicit_server_port(
        self, mock_server_cls, _mock_server_pool_cls
    ):
        with patch('python_apis.apis.ad_api.ssl.create_default_context'):
            ADConnection(
                ['ldaps://directory.example.test:1636'],
                self.search_base,
                tls=ADTLSConfig.secure(),
            )

        mock_server_cls.assert_called_once_with(
            'directory.example.test',
            use_ssl=True,
            tls=ANY,
            port=1636,
        )

    def test_invalid_explicit_tls_fails_before_ldap_construction(self):
        context = MagicMock()
        context.load_verify_locations.side_effect = ssl.SSLError('TLS_VALUE_CANARY')

        with patch(
            'python_apis.apis.ad_api.ssl.create_default_context', return_value=context
        ), patch('python_apis.apis.ad_api.Server') as mock_server_cls, self.assertRaisesRegex(
            ValueError, '^Invalid TLS trust or cipher configuration$'
        ) as captured_error:
            ADConnection(
                self.servers,
                self.search_base,
                tls=ADTLSConfig.secure(ca_certs_data='INVALID_CA_CANARY'),
            )

        mock_server_cls.assert_not_called()
        self.mock_connection_cls.assert_not_called()
        self.assertNotIn('TLS_VALUE_CANARY', str(captured_error.exception))
        self.assertNotIn('INVALID_CA_CANARY', str(captured_error.exception))

    def test_legacy_leaf_key_mode_keeps_validation_and_warns_without_values(self):
        context = MagicMock()
        tls_config = ADTLSConfig.secure(legacy_leaf_key_compatibility=True)

        with patch(
            'python_apis.apis.ad_api.ssl.create_default_context', return_value=context
        ), patch('python_apis.apis.ad_api.Tls') as mock_tls, patch(
            'python_apis.apis.ad_api.Server'
        ), patch('python_apis.apis.ad_api.ServerPool'), self.assertLogs(
            'python_apis.apis.ad_api', level='WARNING'
        ) as captured_logs:
            ADConnection(self.servers, self.search_base, tls=tls_config)

        context.set_ciphers.assert_called_once_with('DEFAULT:@SECLEVEL=1')
        self.assertEqual(mock_tls.call_count, 2)
        for tls_call in mock_tls.call_args_list:
            self.assertEqual(tls_call.kwargs['validate'], ssl.CERT_REQUIRED)
            self.assertEqual(tls_call.kwargs['ciphers'], 'DEFAULT:@SECLEVEL=1')
        logs = '\n'.join(captured_logs.output)
        self.assertIn('certificate and hostname validation remain required', logs)
        self.assertNotIn('server1', logs)

    def test_rebind_reuses_explicit_tls_config(self):
        tls_config = ADTLSConfig.secure()
        with patch('python_apis.apis.ad_api.ssl.create_default_context'), patch(
            'python_apis.apis.ad_api.Tls'
        ) as mock_tls, patch('python_apis.apis.ad_api.Server'), patch(
            'python_apis.apis.ad_api.ServerPool'
        ):
            connection = ADConnection(self.servers, self.search_base, tls=tls_config)
            mock_tls.reset_mock()

            connection.rebind()

        self.assertIs(connection.tls_config, tls_config)
        self.assertEqual(mock_tls.call_count, 2)

    @patch('python_apis.apis.ad_api.ServerPool')
    @patch('python_apis.apis.ad_api.Server')
    def test_custom_connection_options_are_stored_and_forwarded(
        self, mock_server_cls, _mock_server_pool_cls
    ):
        conn = ADConnection(
            self.servers,
            self.search_base,
            receive_timeout=30,
            connect_timeout=4.5,
            page_size=250,
            read_retry_count=3,
            read_retry_backoff_seconds=0.25,
            write_retry_count=2,
        )

        self.assertEqual(conn.receive_timeout, 30)
        self.assertEqual(conn.connect_timeout, 4.5)
        self.assertEqual(conn.page_size, 250)
        self.assertEqual(conn.read_retry_count, 3)
        self.assertEqual(conn.read_retry_backoff_seconds, 0.25)
        self.assertEqual(conn.write_retry_count, 2)
        mock_server_cls.assert_has_calls([
            call(server, use_ssl=True, tls=ANY, connect_timeout=4.5)
            for server in self.servers
        ])
        self.assertEqual(self.mock_connection_cls.call_args.kwargs['receive_timeout'], 30)

    @patch('python_apis.apis.ad_api.ServerPool')
    @patch('python_apis.apis.ad_api.Server')
    def test_rebind_preserves_custom_connection_options(
        self, mock_server_cls, _mock_server_pool_cls
    ):
        conn = ADConnection(
            self.servers,
            self.search_base,
            receive_timeout=30,
            connect_timeout=7,
        )
        mock_server_cls.reset_mock()
        self.mock_connection_cls.reset_mock()

        conn.rebind()

        mock_server_cls.assert_has_calls([
            call(server, use_ssl=True, tls=ANY, connect_timeout=7)
            for server in self.servers
        ])
        self.assertEqual(self.mock_connection_cls.call_args.kwargs['receive_timeout'], 30)

    def test_invalid_connection_options_fail_before_ldap_objects_are_created(self):
        invalid_options = [
            ('receive_timeout', {'receive_timeout': 0}),
            ('receive_timeout', {'receive_timeout': float('nan')}),
            ('receive_timeout', {'receive_timeout': float('inf')}),
            ('connect_timeout', {'connect_timeout': -1}),
            ('connect_timeout', {'connect_timeout': float('nan')}),
            ('page_size', {'page_size': 0}),
            ('read_retry_count', {'read_retry_count': -1}),
            ('read_retry_backoff_seconds', {'read_retry_backoff_seconds': -0.1}),
            ('read_retry_backoff_seconds', {'read_retry_backoff_seconds': float('nan')}),
            ('read_retry_backoff_seconds', {'read_retry_backoff_seconds': float('inf')}),
            ('write_retry_count', {'write_retry_count': -1}),
        ]

        for option_name, options in invalid_options:
            with self.subTest(option=option_name), patch(
                'python_apis.apis.ad_api.Server'
            ) as mock_server_cls:
                self.mock_connection_cls.reset_mock()

                with self.assertRaisesRegex(ValueError, option_name):
                    ADConnection(self.servers, self.search_base, **options)

                mock_server_cls.assert_not_called()
                self.mock_connection_cls.assert_not_called()

    def test_search(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        mock_result = [{'attributes': {'cn': 'John Doe', 'mail': 'john@example.com'}}]
        self.mock_connection.extend.standard.paged_search.return_value = iter(mock_result)

        results = ad_conn.search('(objectClass=user)', ['cn', 'mail'])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['cn'], 'John Doe')
        self.mock_connection.extend.standard.paged_search.assert_called_once_with(
            search_base=self.search_base,
            search_filter='(objectClass=user)',
            search_scope=SUBTREE,
            attributes=['cn', 'mail'],
            paged_size=500,
            generator=True,
        )

    def test_legacy_search_can_represent_rejected_result_as_empty(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.return_value = iter([])
        self.mock_connection.result = {
            'result': 50,
            'description': 'insufficientAccessRights',
        }

        results = ad_conn.search('(objectClass=user)', ['sAMAccountName'])

        self.assertEqual(results, [])

    def test_strict_search_distinguishes_successful_empty_result(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.return_value = iter([])
        self.mock_connection.result = {'result': 0, 'description': 'success'}

        results = ad_conn.search_strict('(objectClass=user)', ['sAMAccountName'])

        self.assertEqual(results, [])

    def test_strict_search_raises_for_rejected_empty_result(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.return_value = iter([])
        self.mock_connection.result = {
            'result': 50,
            'description': 'LDAP_DIAGNOSTIC_CANARY',
        }

        with self.assertRaises(ADQueryRejectedError) as captured_error:
            ad_conn.search_strict('(cn=FILTER_CANARY)', ['sAMAccountName'])

        error = captured_error.exception
        self.assertEqual(error.error_code, AD_PERMISSION_DENIED)
        self.assertEqual(error.result_code, 50)
        self.assertNotIn('FILTER_CANARY', str(error))
        self.assertNotIn('LDAP_DIAGNOSTIC_CANARY', str(error))

    def test_strict_search_discards_partial_rejected_page(self):
        ad_conn = ADConnection(self.servers, self.search_base)

        def rejected_page():
            yield {'attributes': {'sAMAccountName': 'PARTIAL_MEMBER_CANARY'}}
            self.mock_connection.result = {'result': 50}

        self.mock_connection.extend.standard.paged_search.return_value = rejected_page()

        with self.assertRaises(ADQueryRejectedError) as captured_error:
            ad_conn.search_strict('(objectClass=user)', ['sAMAccountName'])

        self.assertNotIn('PARTIAL_MEMBER_CANARY', str(captured_error.exception))

    def test_strict_search_rejects_malformed_result(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.return_value = iter([])
        self.mock_connection.result = {'description': 'MALFORMED_RESULT_CANARY'}

        with self.assertRaises(ADMalformedResultError) as captured_error:
            ad_conn.search_strict('(objectClass=user)', ['sAMAccountName'])

        self.assertNotIn('MALFORMED_RESULT_CANARY', str(captured_error.exception))

    def test_strict_search_wraps_malformed_filter_safely(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.side_effect = LDAPInvalidFilterError(
            'FILTER_CANARY'
        )

        with self.assertRaises(ADMalformedQueryError) as captured_error:
            ad_conn.search_strict('(cn=FILTER_CANARY', ['sAMAccountName'])

        self.assertNotIn('FILTER_CANARY', str(captured_error.exception))

    def test_strict_search_retries_recoverable_failure_once(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.side_effect = [
            LDAPCommunicationError('TRANSPORT_CANARY'),
            iter([{'attributes': {'sAMAccountName': 'user1'}}]),
        ]
        self.mock_connection.result = {'result': 0}

        with patch.object(ad_conn, '_rebind_after_failure') as mock_rebind:
            results = ad_conn.search_strict('(objectClass=user)', ['sAMAccountName'])

        self.assertEqual(results, [{'sAMAccountName': 'user1'}])
        mock_rebind.assert_called_once()
        self.assertEqual(ad_conn.last_retry_telemetry.operation_name, 'search_strict')
        self.assertEqual(ad_conn.last_retry_telemetry.retry_count, 1)

    def test_strict_search_wraps_exhausted_transport_safely(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.side_effect = LDAPCommunicationError(
            'TRANSPORT_CANARY'
        )

        with patch.object(ad_conn, '_rebind_after_failure'), self.assertRaises(
            ADTransportError
        ) as captured_error:
            ad_conn.search_strict('(cn=FILTER_CANARY)', ['sAMAccountName'])

        self.assertNotIn('TRANSPORT_CANARY', str(captured_error.exception))
        self.assertNotIn('FILTER_CANARY', str(captured_error.exception))
        self.assertEqual(ad_conn.last_retry_telemetry.retry_count, 1)

    def test_strict_search_wraps_timeout_without_retry(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.side_effect = LDAPResponseTimeoutError(
            'TIMEOUT_CANARY'
        )

        with patch.object(ad_conn, '_rebind_after_failure') as mock_rebind, self.assertRaises(
            ADTimeoutError
        ) as captured_error:
            ad_conn.search_strict('(cn=FILTER_CANARY)', ['sAMAccountName'])

        mock_rebind.assert_not_called()
        self.assertNotIn('TIMEOUT_CANARY', str(captured_error.exception))

    def test_search_extracts_ou_after_complete_escaped_rdn(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.return_value = iter([
            {
                'attributes': {
                    'distinguishedName': (
                        r'CN=Doe\, Jane+UID=jdoe,OU=Users,DC=example,DC=com'
                    ),
                },
            },
        ])

        results = ad_conn.search('(objectClass=user)', ['distinguishedName'])

        self.assertEqual(results[0]['ou'], 'OU=Users,DC=example,DC=com')

    def test_search_forwards_custom_base_scope_and_page_size(self):
        ad_conn = ADConnection(self.servers, self.search_base, page_size=250)
        self.mock_connection.extend.standard.paged_search.return_value = iter([])

        ad_conn.search(
            '(objectClass=organizationalUnit)',
            ['distinguishedName'],
            search_base='OU=Departments,DC=example,DC=com',
            search_scope=LEVEL,
            page_size=25,
        )

        self.mock_connection.extend.standard.paged_search.assert_called_once_with(
            search_base='OU=Departments,DC=example,DC=com',
            search_filter='(objectClass=organizationalUnit)',
            search_scope=LEVEL,
            attributes=['distinguishedName'],
            paged_size=25,
            generator=True,
        )
        self.assertEqual(ad_conn.page_size, 250)

    def test_search_accepts_standard_ldap_scopes(self):
        ad_conn = ADConnection(self.servers, self.search_base)

        for search_scope in (BASE, LEVEL, SUBTREE):
            with self.subTest(search_scope=search_scope):
                self.mock_connection.extend.standard.paged_search.reset_mock()
                self.mock_connection.extend.standard.paged_search.return_value = iter([])

                ad_conn.search('(objectClass=*)', search_scope=search_scope)

                self.assertEqual(
                    self.mock_connection.extend.standard.paged_search.call_args.kwargs[
                        'search_scope'
                    ],
                    search_scope,
                )

    def test_invalid_search_options_fail_before_paged_search(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        invalid_options = [
            ('search_base', {'search_base': ''}),
            ('search_scope', {'search_scope': 'INVALID'}),
            ('page_size', {'page_size': 0}),
        ]

        for option_name, options in invalid_options:
            with self.subTest(option=option_name):
                self.mock_connection.extend.standard.paged_search.reset_mock()

                with self.assertRaisesRegex(ValueError, option_name):
                    ad_conn.search('(objectClass=*)', **options)

                self.mock_connection.extend.standard.paged_search.assert_not_called()

    def test_get_v2_with_results(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        mock_result = [{'attributes': {'cn': 'John Doe'}}]
        self.mock_connection.extend.standard.paged_search.return_value = iter(mock_result)

        result = ad_conn.get_v2('(objectClass=user)', ['cn'])

        self.assertTrue(result.found)
        self.assertEqual(result.item['cn'], 'John Doe')
        self.assertIsNone(result.not_found_reason)
        self.assertIsNone(result.error_code)

    def test_get_v2_returns_first_of_many(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        mock_result = [
            {'attributes': {'cn': 'First'}},
            {'attributes': {'cn': 'Second'}},
        ]
        self.mock_connection.extend.standard.paged_search.return_value = iter(mock_result)

        result = ad_conn.get_v2('(objectClass=user)', ['cn'])

        self.assertTrue(result.found)
        self.assertEqual(result.item['cn'], 'First')

    def test_get_v2_no_results(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.return_value = iter([])

        result = ad_conn.get_v2('(objectClass=user)', ['cn'])

        self.assertFalse(result.found)
        self.assertIsNone(result.item)
        self.assertEqual(result.not_found_reason, 'no_match')
        self.assertEqual(result.error_code, 'AD_NOT_FOUND')

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

    def test_rename_dn(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        distinguished_name = 'CN=John Doe,OU=users,DC=example,DC=com'
        new_relative_dn = 'CN=John Smith'

        self.mock_connection.modify_dn.return_value = True
        self.mock_connection.result = {'description': 'success'}

        result = ad_conn.rename_dn(distinguished_name, new_relative_dn)

        self.mock_connection.modify_dn.assert_called_once_with(
            distinguished_name,
            new_relative_dn,
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], {'description': 'success'})

    def test_force_change_password_at_next_logon_force_true(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        distinguished_name = 'CN=John Doe,OU=users,DC=example,DC=com'

        self.mock_connection.modify.return_value = True
        self.mock_connection.result = {'description': 'success'}

        result = ad_conn.force_change_password_at_next_logon(distinguished_name, force=True)

        expected_changes = {'pwdLastSet': [MODIFY_REPLACE, 0]}
        self.mock_connection.modify.assert_called_once_with(distinguished_name, expected_changes)
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], {'description': 'success'})

    def test_force_change_password_at_next_logon_force_false(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        distinguished_name = 'CN=John Doe,OU=users,DC=example,DC=com'

        self.mock_connection.modify.return_value = True
        self.mock_connection.result = {'description': 'success'}

        result = ad_conn.force_change_password_at_next_logon(distinguished_name, force=False)

        expected_changes = {'pwdLastSet': [MODIFY_REPLACE, -1]}
        self.mock_connection.modify.assert_called_once_with(distinguished_name, expected_changes)
        self.assertTrue(result['success'])


class TestAutoReconnect(unittest.TestCase):
    """Tests for the automatic rebind-on-failure behaviour."""

    def setUp(self):
        self.servers = ['ldap://server1', 'ldap://server2']
        self.search_base = 'dc=example,dc=com'

        patcher = patch('python_apis.apis.ad_api.Connection')
        self.mock_connection_cls = patcher.start()
        self.mock_connection = MagicMock()
        self.mock_connection.bind.return_value = True
        self.mock_connection_cls.return_value = self.mock_connection
        self.addCleanup(patcher.stop)

    # -- rebind ---------------------------------------------------------

    def test_rebind_creates_new_connection(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        old_connection = ad_conn.connection

        new_mock_connection = MagicMock()
        new_mock_connection.bind.return_value = True
        self.mock_connection_cls.return_value = new_mock_connection

        ad_conn.rebind()

        self.assertIsNot(ad_conn.connection, old_connection)
        self.mock_connection.unbind.assert_called_once()

    def test_rebind_still_works_when_unbind_raises_session_terminated(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.unbind.side_effect = LDAPSessionTerminatedByServerError()

        ad_conn.rebind()  # should not raise

        self.assertIsNotNone(ad_conn.connection)

    def test_rebind_still_works_when_unbind_raises_communication_error(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.unbind.side_effect = LDAPCommunicationError()

        ad_conn.rebind()  # should not raise

        self.assertIsNotNone(ad_conn.connection)

    def test_rebind_still_works_when_unbind_raises_os_error(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.unbind.side_effect = OSError("socket closed")

        ad_conn.rebind()  # should not raise

        self.assertIsNotNone(ad_conn.connection)

    def test_close_is_idempotent(self):
        ad_conn = ADConnection(self.servers, self.search_base)

        ad_conn.close()
        ad_conn.close()

        self.mock_connection.unbind.assert_called_once_with()

    def test_context_manager_returns_and_closes_connection(self):
        ad_conn = ADConnection(self.servers, self.search_base)

        with ad_conn as entered_connection:
            self.assertIs(entered_connection, ad_conn)
            self.mock_connection.unbind.assert_not_called()

        self.mock_connection.unbind.assert_called_once_with()

    def test_context_manager_closes_and_propagates_original_error(self):
        ad_conn = ADConnection(self.servers, self.search_base)

        with self.assertRaisesRegex(RuntimeError, "ORIGINAL_ERROR_CANARY"):
            with ad_conn:
                raise RuntimeError("ORIGINAL_ERROR_CANARY")

        self.mock_connection.unbind.assert_called_once_with()

    def test_context_cleanup_failure_does_not_mask_original_error(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.unbind.side_effect = LDAPCommunicationError(
            "CLEANUP_ERROR_CANARY"
        )

        with self.assertRaisesRegex(RuntimeError, "ORIGINAL_ERROR_CANARY"):
            with ad_conn:
                raise RuntimeError("ORIGINAL_ERROR_CANARY")

    def test_rebind_reopens_lifecycle_and_preserves_options(self):
        tls_config = ADTLSConfig.secure()
        ad_conn = ADConnection(
            self.servers,
            self.search_base,
            authentication="simple",
            username="SIMPLE_USER_CANARY",
            password="SIMPLE_PASSWORD_CANARY",
            tls=tls_config,
            receive_timeout=30,
            read_retry_count=2,
        )

        ad_conn.rebind()
        ad_conn.close()

        self.assertEqual(self.mock_connection.unbind.call_count, 2)
        self.assertIs(ad_conn.tls_config, tls_config)
        self.assertEqual(ad_conn.authentication_mode, "simple")
        self.assertEqual(ad_conn.receive_timeout, 30)
        self.assertEqual(ad_conn.read_retry_count, 2)

    # -- decorator: retry on session error ------------------------------

    def test_search_retries_on_session_terminated(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        good_result = [{'attributes': {'cn': 'Jane Doe'}}]
        self.mock_connection.extend.standard.paged_search.side_effect = [
            LDAPSessionTerminatedByServerError(),
            iter(good_result),
        ]

        results = ad_conn.search('(cn=Jane Doe)', ['cn'])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['cn'], 'Jane Doe')

    def test_retry_warning_omits_filter_exception_and_server_canaries(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        filter_canary = 'TASK0_FILTER_CANARY'
        exception_canary = 'TASK0_EXCEPTION_CANARY'
        self.mock_connection.extend.standard.paged_search.side_effect = [
            LDAPCommunicationError(exception_canary),
            iter([]),
        ]

        with patch.object(ad_conn, '_rebind_after_failure'), self.assertLogs(
            'python_apis.apis.ad_api', level='WARNING'
        ) as captured_logs:
            ad_conn.search(f'(cn={filter_canary})', ['cn'])

        logs = '\n'.join(captured_logs.output)
        self.assertNotIn(filter_canary, logs)
        self.assertNotIn(exception_canary, logs)
        self.assertNotIn('server1', logs)
        self.assertNotIn('server2', logs)

    def test_search_discards_partial_entries_before_retry(self):
        ad_conn = ADConnection(self.servers, self.search_base)

        def interrupted_page():
            yield {'attributes': {'cn': 'Partial Result'}}
            raise LDAPCommunicationError('connection lost after partial page')

        complete_result = [{'attributes': {'cn': 'Complete Result'}}]
        self.mock_connection.extend.standard.paged_search.side_effect = [
            interrupted_page(),
            iter(complete_result),
        ]

        with patch.object(ad_conn, '_rebind_after_failure') as mock_rebind:
            results = ad_conn.search('(objectClass=user)', ['cn'])

        mock_rebind.assert_called_once()
        self.assertEqual(results, [{'cn': 'Complete Result'}])

    def test_modify_retries_on_communication_error_when_explicitly_enabled(self):
        ad_conn = ADConnection(self.servers, self.search_base, write_retry_count=1)
        self.mock_connection.modify.side_effect = [
            LDAPCommunicationError(),
            True,
        ]
        self.mock_connection.result = {'description': 'success'}

        result = ad_conn.modify(
            'CN=John,OU=users,DC=example,DC=com',
            [('department', 'IT')],
        )

        self.assertTrue(result['success'])

    def test_modify_does_not_retry_communication_error_by_default(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.modify.side_effect = LDAPCommunicationError('write response lost')

        with patch.object(ad_conn, '_rebind_after_failure') as mock_rebind:
            with self.assertRaises(LDAPCommunicationError):
                ad_conn.modify(
                    'CN=John,OU=users,DC=example,DC=com',
                    [('department', 'IT')],
                )

        mock_rebind.assert_not_called()
        self.assertEqual(ad_conn.last_retry_telemetry.retry_count, 0)
        self.assertEqual(ad_conn.last_retry_telemetry.policy['strategy'], 'no_retry')

    def test_search_respects_zero_read_retries(self):
        ad_conn = ADConnection(self.servers, self.search_base, read_retry_count=0)
        self.mock_connection.extend.standard.paged_search.side_effect = LDAPCommunicationError(
            'read failed'
        )

        with patch.object(ad_conn, '_rebind_after_failure') as mock_rebind:
            with self.assertRaises(LDAPCommunicationError):
                ad_conn.search('(objectClass=user)', ['cn'])

        mock_rebind.assert_not_called()
        self.assertEqual(ad_conn.last_retry_telemetry.retry_count, 0)

    def test_search_supports_multiple_bounded_retries(self):
        ad_conn = ADConnection(self.servers, self.search_base, read_retry_count=2)
        complete_result = [{'attributes': {'cn': 'Complete Result'}}]
        self.mock_connection.extend.standard.paged_search.side_effect = [
            LDAPCommunicationError('first'),
            LDAPSessionTerminatedByServerError('second'),
            iter(complete_result),
        ]

        with patch.object(ad_conn, '_rebind_after_failure') as mock_rebind:
            results = ad_conn.search('(objectClass=user)', ['cn'])

        self.assertEqual(results, [{'cn': 'Complete Result'}])
        self.assertEqual(mock_rebind.call_count, 2)
        self.assertEqual(ad_conn.last_retry_telemetry.retry_count, 2)
        self.assertEqual(ad_conn.last_retry_telemetry.policy['max_attempts'], 3)

    @patch('python_apis.apis.ad_api.time.sleep')
    @patch('python_apis.apis.ad_api.ServerPool')
    @patch('python_apis.apis.ad_api.Server')
    def test_retry_closes_backs_off_and_prioritizes_another_controller(
        self,
        mock_server_cls,
        _mock_server_pool_cls,
        mock_sleep,
    ):
        failed_connection = MagicMock()
        failed_connection.bind.return_value = True
        failed_connection.server.host = 'server1'
        failed_connection.extend.standard.paged_search.side_effect = LDAPCommunicationError(
            'server1 response lost'
        )
        recovered_connection = MagicMock()
        recovered_connection.bind.return_value = True
        recovered_connection.server.host = 'server2'
        recovered_connection.extend.standard.paged_search.return_value = iter([
            {'attributes': {'cn': 'Recovered'}},
        ])
        self.mock_connection_cls.side_effect = [failed_connection, recovered_connection]

        with self.assertLogs('python_apis.apis.ad_api', level='WARNING') as captured_logs:
            ad_conn = ADConnection(
                self.servers,
                self.search_base,
                read_retry_backoff_seconds=0.5,
            )
            results = ad_conn.search('(objectClass=user)', ['cn'])

        self.assertEqual(results, [{'cn': 'Recovered'}])
        failed_connection.unbind.assert_called_once()
        mock_sleep.assert_called_once_with(0.5)
        self.assertEqual(
            [server_call.args[0] for server_call in mock_server_cls.call_args_list],
            [
                'ldap://server1',
                'ldap://server2',
                'ldap://server2',
                'ldap://server1',
            ],
        )
        logs = '\n'.join(captured_logs.output)
        self.assertIn('controller-', logs)
        self.assertNotIn('server1', logs)
        telemetry = ad_conn.last_retry_telemetry
        self.assertEqual(telemetry.attempt_count, 2)
        self.assertTrue(telemetry.failed_server.startswith('controller-'))
        self.assertTrue(telemetry.selected_server.startswith('controller-'))
        self.assertNotEqual(telemetry.failed_server, telemetry.selected_server)

    @patch('python_apis.apis.ad_api.ServerPool')
    @patch('python_apis.apis.ad_api.Server')
    def test_single_controller_retry_keeps_available_controller(
        self, mock_server_cls, _mock_server_pool_cls
    ):
        only_server = ['ldap://server1']
        failed_connection = MagicMock()
        failed_connection.bind.return_value = True
        failed_connection.server.host = 'server1'
        failed_connection.extend.standard.paged_search.side_effect = LDAPCommunicationError()
        recovered_connection = MagicMock()
        recovered_connection.bind.return_value = True
        recovered_connection.server.host = 'server1'
        recovered_connection.extend.standard.paged_search.return_value = iter([])
        self.mock_connection_cls.side_effect = [failed_connection, recovered_connection]

        ad_conn = ADConnection(only_server, self.search_base)
        ad_conn.search('(objectClass=user)', ['cn'])

        self.assertEqual(
            [server_call.args[0] for server_call in mock_server_cls.call_args_list],
            ['ldap://server1', 'ldap://server1'],
        )

    # -- decorator: non-recoverable errors propagate --------------------

    def test_search_does_not_retry_on_value_error(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.side_effect = ValueError("bad filter")

        with self.assertRaises(ValueError):
            ad_conn.search('bad', ['cn'])

    # -- decorator: second attempt also fails ---------------------------

    def test_search_propagates_error_when_retry_also_fails(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.extend.standard.paged_search.side_effect = (
            LDAPSessionTerminatedByServerError()
        )

        with self.assertRaises(LDAPSessionTerminatedByServerError):
            ad_conn.search('(cn=Ghost)', ['cn'])

    # -- rebind failure propagates ADConnectionError --------------------

    def test_rebind_failure_propagates_connection_error(self):
        ad_conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.bind.return_value = False
        self.mock_connection.result = {'description': 'Kerberos expired'}

        with self.assertRaises(ADConnectionError):
            ad_conn.rebind()


if __name__ == '__main__':
    unittest.main()
