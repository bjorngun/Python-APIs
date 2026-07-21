"""Security-hygiene tests for reusable Active Directory connections and reads."""

import ssl
import unittest
from unittest.mock import MagicMock, call, patch

from ldap3.core.exceptions import LDAPCommunicationError

from python_apis.apis import ADConnection, ADTLSConfig
from python_apis.apis.ad_errors import (
    ADMalformedResultError,
    ADQueryRejectedError,
    ADTLSConfigurationError,
)
from python_apis.services import ADMembershipService

USERNAME_CANARY = "SECURITY_USERNAME_CANARY"
PASSWORD_CANARY = "SECURITY_PASSWORD_CANARY"
FILTER_CANARY = "SECURITY_FILTER_CANARY"
DN_CANARY = "CN=SECURITY_DN_CANARY,DC=example,DC=test"
GROUP_CANARY = "SECURITY_GROUP_CANARY"
MEMBER_CANARY = "SECURITY_MEMBER_CANARY"
ATTRIBUTE_CANARY = "SECURITY_ATTRIBUTE_CANARY"
CA_CANARY = "SECURITY_CA_CANARY"
SERVER_CANARY = "SECURITY_SERVER_CANARY"
EXCEPTION_CANARY = "SECURITY_EXCEPTION_CANARY"

SENSITIVE_CANARIES = (
    USERNAME_CANARY,
    PASSWORD_CANARY,
    FILTER_CANARY,
    DN_CANARY,
    GROUP_CANARY,
    MEMBER_CANARY,
    ATTRIBUTE_CANARY,
    CA_CANARY,
    SERVER_CANARY,
    EXCEPTION_CANARY,
)


class TestADSecurityHygiene(unittest.TestCase):
    """Prove supported diagnostics omit caller and directory values."""

    def setUp(self):
        connection_patcher = patch("python_apis.apis.ad_api.Connection")
        self.connection_class = connection_patcher.start()
        self.addCleanup(connection_patcher.stop)
        self.ldap_connection = MagicMock()
        self.ldap_connection.bind.return_value = True
        self.ldap_connection.server.host = SERVER_CANARY
        self.connection_class.return_value = self.ldap_connection

    def assert_no_sensitive_values(self, output: object) -> None:
        """Assert every issue #54 canary is absent from supported output."""

        text = str(output)
        for canary in SENSITIVE_CANARIES:
            with self.subTest(canary=canary):
                self.assertNotIn(canary, text)

    @patch("python_apis.apis.ad_api.set_library_log_detail_level")
    @patch("python_apis.apis.ad_api.set_library_log_hide_sensitive_data")
    def test_default_construction_does_not_enable_ldap_logging(
        self, mock_hide_sensitive, mock_detail_level
    ):
        ADConnection([f"ldaps://{SERVER_CANARY}"], "DC=example,DC=test")

        mock_hide_sensitive.assert_not_called()
        mock_detail_level.assert_not_called()

    def test_opt_in_logging_hides_sensitive_data_before_enabling_detail(self):
        calls = MagicMock()
        with patch(
            "python_apis.apis.ad_api.set_library_log_hide_sensitive_data",
            side_effect=lambda value: calls("hide", value),
        ), patch(
            "python_apis.apis.ad_api.set_library_log_detail_level",
            side_effect=lambda value: calls("detail", value),
        ):
            ADConnection(
                [f"ldaps://{SERVER_CANARY}"],
                "DC=example,DC=test",
                enable_ldap_logging=True,
            )

        self.assertEqual(
            calls.call_args_list,
            [call("hide", True), call("detail", unittest.mock.ANY)],
        )

    def test_simple_bind_supported_representations_are_redacted(self):
        with patch("python_apis.apis.ad_api.ssl.create_default_context"):
            connection = ADConnection(
                [f"ldaps://{SERVER_CANARY}"],
                "DC=example,DC=test",
                authentication="simple",
                username=USERNAME_CANARY,
                password=PASSWORD_CANARY,
                tls=ADTLSConfig.secure(ca_certs_data=CA_CANARY),
            )

        self.assert_no_sensitive_values(repr(connection))
        self.assert_no_sensitive_values(repr(connection.tls_config))
        self.assertIsNone(connection.connection.user)
        self.assertIsNone(connection.connection.password)

    def test_invalid_tls_safe_error_omits_config_and_cause_values(self):
        context = MagicMock()
        context.load_verify_locations.side_effect = ssl.SSLError(EXCEPTION_CANARY)

        with patch(
            "python_apis.apis.ad_api.ssl.create_default_context",
            return_value=context,
        ), self.assertRaises(ADTLSConfigurationError) as captured_error:
            ADConnection(
                [f"ldaps://{SERVER_CANARY}"],
                "DC=example,DC=test",
                tls=ADTLSConfig.secure(ca_certs_data=CA_CANARY),
            )

        self.assert_no_sensitive_values(captured_error.exception)

    def test_legacy_leaf_key_warning_is_value_free_and_validation_specific(self):
        context = MagicMock()
        with patch(
            "python_apis.apis.ad_api.ssl.create_default_context",
            return_value=context,
        ), self.assertLogs("python_apis.apis.ad_api", level="WARNING") as captured:
            ADConnection(
                [f"ldaps://{SERVER_CANARY}"],
                "DC=example,DC=test",
                tls=ADTLSConfig.secure(legacy_leaf_key_compatibility=True),
            )

        output = "\n".join(captured.output)
        self.assertIn("certificate and hostname validation remain required", output)
        self.assert_no_sensitive_values(output)

    def test_retry_log_and_telemetry_are_aggregate_only(self):
        connection = ADConnection(
            [f"ldaps://{SERVER_CANARY}"],
            "DC=example,DC=test",
        )
        self.ldap_connection.extend.standard.paged_search.side_effect = [
            LDAPCommunicationError(EXCEPTION_CANARY),
            iter([]),
        ]
        self.ldap_connection.result = {"result": 0}

        with patch.object(connection, "_rebind_after_failure"), self.assertLogs(
            "python_apis.apis.ad_api", level="WARNING"
        ) as captured:
            connection.search_strict(
                f"(sAMAccountName={FILTER_CANARY})",
                [ATTRIBUTE_CANARY],
            )

        telemetry = connection.last_retry_telemetry
        self.assertIsNotNone(telemetry)
        self.assertEqual(telemetry.operation_name, "search_strict")
        self.assert_no_sensitive_values("\n".join(captured.output))
        self.assert_no_sensitive_values(telemetry)

    def test_rejected_search_and_malformed_member_errors_are_value_free(self):
        connection = MagicMock()
        service = ADMembershipService(connection)
        connection.search_strict.side_effect = ADQueryRejectedError(
            error_code="AD_PERMISSION_DENIED",
            result_code=50,
            controller="controller-deadbeef",
        )

        with self.assertRaises(ADQueryRejectedError) as rejected_error:
            service.resolve_group_dn(GROUP_CANARY)

        self.assert_no_sensitive_values(rejected_error.exception)

        connection.search_strict.side_effect = None
        connection.search_strict.return_value = [
            {"distinguishedName": DN_CANARY},
        ]
        with patch.object(
            service,
            "resolve_group_dn",
            return_value=MagicMock(
                found=True,
                item={"distinguishedName": DN_CANARY},
            ),
        ):
            connection.search_strict.return_value = [
                {"sAMAccountName": MEMBER_CANARY},
                {"sAMAccountName": None},
            ]
            with self.assertRaises(ADMalformedResultError) as malformed_error:
                service.get_transitive_enabled_group_members(GROUP_CANARY)

        self.assert_no_sensitive_values(malformed_error.exception)

    def test_cleanup_debug_log_is_value_free(self):
        connection = ADConnection(
            [f"ldaps://{SERVER_CANARY}"],
            "DC=example,DC=test",
        )
        self.ldap_connection.unbind.side_effect = LDAPCommunicationError(
            EXCEPTION_CANARY
        )

        with self.assertLogs("python_apis.apis.ad_api", level="DEBUG") as captured:
            connection.close()

        self.assert_no_sensitive_values("\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
