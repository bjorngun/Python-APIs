"""Tests for secure AD connection and authorization examples."""

import unittest
from unittest.mock import MagicMock, patch

from examples import secure_ad_connection
from python_apis.apis import ADConnectionError


class TestSecureADConnectionExample(unittest.TestCase):
    """Verify explicit secure configuration and value-free output."""

    @patch("examples.secure_ad_connection.ADConnection")
    @patch("examples.secure_ad_connection.ADTLSConfig.secure")
    def test_build_connection_uses_explicit_secure_tls(
        self, mock_secure_tls, mock_connection
    ):
        secure_tls = MagicMock()
        mock_secure_tls.return_value = secure_tls
        environment = {
            "LDAP_SERVER_LIST": "directory-a directory-b",
            "SEARCH_BASE": "DC=example,DC=test",
            "LDAP_CA_CERTS_FILE": "configured-ca-file",
            "LDAP_AUTHENTICATION": "simple",
            "LDAP_BIND_USERNAME": "USERNAME_CANARY",
            "LDAP_BIND_PASSWORD": "PASSWORD_CANARY",
        }

        with patch.dict("os.environ", environment, clear=True):
            secure_ad_connection.build_connection()

        mock_secure_tls.assert_called_once_with(ca_certs_file="configured-ca-file")
        mock_connection.assert_called_once_with(
            ["directory-a", "directory-b"],
            "DC=example,DC=test",
            authentication="simple",
            username="USERNAME_CANARY",
            password="PASSWORD_CANARY",
            tls=secure_tls,
            connect_timeout=5,
            receive_timeout=30,
            read_retry_count=1,
            write_retry_count=0,
        )

    def test_main_prints_only_stable_failure_code(self):
        error = ADConnectionError("RAW_DIRECTORY_DETAIL_CANARY")
        with patch.object(
            secure_ad_connection,
            "build_connection",
            side_effect=error,
        ), patch("builtins.print") as mock_print:
            secure_ad_connection.main()

        output = " ".join(str(argument) for argument in mock_print.call_args.args)
        self.assertIn("AD_CONNECTION_ERROR", output)
        self.assertNotIn("RAW_DIRECTORY_DETAIL_CANARY", output)

    def test_invalid_authentication_mode_raises_safe_configuration_error(self):
        with patch.dict(
            "os.environ",
            {"LDAP_AUTHENTICATION": "UNSUPPORTED_MODE_CANARY"},
            clear=True,
        ), self.assertRaises(ADConnectionError) as captured_error:
            secure_ad_connection.build_connection()

        self.assertEqual(captured_error.exception.error_code, "AD_VALIDATION_ERROR")
        self.assertNotIn("UNSUPPORTED_MODE_CANARY", str(captured_error.exception))


if __name__ == "__main__":
    unittest.main()
