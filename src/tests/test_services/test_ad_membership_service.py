"""Tests for strict AD-only membership queries."""

import unittest
from unittest.mock import MagicMock, patch

from ldap3.core.exceptions import LDAPCommunicationError

from python_apis.apis import ADConnection, escape_filter_value
from python_apis.apis.ad_errors import (
    ADMalformedQueryError,
    ADMalformedResultError,
    ADQueryRejectedError,
    ADTransportError,
)
from python_apis.models import ADGetResult
from python_apis.services import ADMembershipService
from python_apis.services.ad_membership_service import (
    LDAP_MATCHING_RULE_BIT_AND,
    LDAP_MATCHING_RULE_IN_CHAIN,
)


class TestEscapeFilterValue(unittest.TestCase):
    """Verify RFC 4515 escaping of every special caller character."""

    def test_escapes_filter_metacharacters_and_nul(self):
        self.assertEqual(
            escape_filter_value("*()\\\x00"),
            r"\2a\28\29\5c\00",
        )

    def test_rejects_non_string_values(self):
        with self.assertRaisesRegex(TypeError, "must be a string"):
            escape_filter_value(123)


class TestADMembershipServiceGroupLookup(unittest.TestCase):
    """Verify strict escaped lookup by stable group identifier."""

    def setUp(self):
        self.connection = MagicMock()
        self.service = ADMembershipService(self.connection)

    def test_resolves_exactly_one_current_group_dn(self):
        self.connection.search_strict.return_value = [
            {"distinguishedName": "CN=Current,OU=Groups,DC=example,DC=test"}
        ]

        with patch(
            "python_apis.services.ad_membership_service.escape_filter_value",
            return_value=r"Group\2a\29\28",
        ) as mock_escape:
            result = self.service.resolve_group_dn("GROUP_FILTER_CANARY")

        mock_escape.assert_called_once_with("GROUP_FILTER_CANARY")
        self.connection.search_strict.assert_called_once_with(
            "(&(objectCategory=group)(objectClass=group)"
            r"(sAMAccountName=Group\2a\29\28))",
            ["distinguishedName"],
        )
        self.assertTrue(result.found)
        self.assertEqual(
            result.item,
            {"distinguishedName": "CN=Current,OU=Groups,DC=example,DC=test"},
        )

    def test_not_found_is_explicit(self):
        self.connection.search_strict.return_value = []

        result = self.service.resolve_group_dn("missing-group")

        self.assertFalse(result.found)
        self.assertEqual(result.not_found_reason, "no_match")
        self.assertEqual(result.error_code, "AD_NOT_FOUND")

    def test_duplicate_groups_fail_closed(self):
        self.connection.search_strict.return_value = [
            {"distinguishedName": "CN=One,DC=example,DC=test"},
            {"distinguishedName": "CN=Two,DC=example,DC=test"},
        ]

        with self.assertRaises(ADMalformedResultError):
            self.service.resolve_group_dn("duplicate-group")

    def test_missing_or_invalid_dn_fails_closed(self):
        invalid_results = (
            {},
            {"distinguishedName": None},
            {"distinguishedName": " "},
            {"distinguishedName": ["CN=Unexpected"]},
        )

        for record in invalid_results:
            with self.subTest(record=record):
                self.connection.search_strict.return_value = [record]
                with self.assertRaises(ADMalformedResultError):
                    self.service.resolve_group_dn("malformed-group")

    def test_empty_identifier_fails_before_search(self):
        for group_id in ("", " ", None):
            with self.subTest(group_id=group_id), self.assertRaises(
                ADMalformedQueryError
            ):
                self.service.resolve_group_dn(group_id)

        self.connection.search_strict.assert_not_called()


class TestADMembershipServiceTransitiveMembers(unittest.TestCase):
    """Verify server-side transitive enabled-user membership reads."""

    def setUp(self):
        self.connection = MagicMock()
        self.service = ADMembershipService(self.connection)

    @patch.object(ADMembershipService, "resolve_group_dn")
    def test_returns_normalized_unique_members(self, mock_resolve):
        group_dn = "CN=Current,OU=Groups,DC=example,DC=test"
        mock_resolve.return_value = ADGetResult.found_item(
            {"distinguishedName": group_dn}
        )
        self.connection.search_strict.return_value = [
            {"sAMAccountName": "User-A"},
            {"sAMAccountName": "user-a"},
            {"sAMAccountName": "USER-B"},
        ]

        with patch(
            "python_apis.services.ad_membership_service.escape_filter_value",
            return_value="ESCAPED_GROUP_DN",
        ) as mock_escape:
            result = self.service.get_transitive_enabled_group_members("stable-group")

        mock_resolve.assert_called_once_with("stable-group")
        mock_escape.assert_called_once_with(group_dn)
        expected_filter = (
            "(&(objectCategory=person)(objectClass=user)"
            f"(!(userAccountControl:{LDAP_MATCHING_RULE_BIT_AND}:=2))"
            f"(memberOf:{LDAP_MATCHING_RULE_IN_CHAIN}:=ESCAPED_GROUP_DN))"
        )
        self.connection.search_strict.assert_called_once_with(
            expected_filter,
            ["sAMAccountName"],
        )
        self.assertTrue(result.group_found)
        self.assertEqual(result.members, ("user-a", "user-b"))

    @patch.object(ADMembershipService, "resolve_group_dn")
    def test_existing_group_with_no_enabled_users_is_valid_empty(self, mock_resolve):
        mock_resolve.return_value = ADGetResult.found_item(
            {"distinguishedName": "CN=Empty,DC=example,DC=test"}
        )
        self.connection.search_strict.return_value = []

        result = self.service.get_transitive_enabled_group_members("empty-group")

        self.assertTrue(result.group_found)
        self.assertEqual(result.members, ())
        self.assertIsNone(result.error_code)

    @patch.object(ADMembershipService, "resolve_group_dn")
    def test_missing_group_is_distinct_and_skips_user_search(self, mock_resolve):
        mock_resolve.return_value = ADGetResult.not_found()

        result = self.service.get_transitive_enabled_group_members("missing-group")

        self.assertFalse(result.group_found)
        self.assertEqual(result.not_found_reason, "group_not_found")
        self.assertEqual(result.error_code, "AD_NOT_FOUND")
        self.connection.search_strict.assert_not_called()

    @patch.object(ADMembershipService, "resolve_group_dn")
    def test_malformed_user_aborts_whole_result(self, mock_resolve):
        mock_resolve.return_value = ADGetResult.found_item(
            {"distinguishedName": "CN=Group,DC=example,DC=test"}
        )
        invalid_users = (
            {},
            {"sAMAccountName": None},
            {"sAMAccountName": " "},
            {"sAMAccountName": ["unexpected"]},
        )

        for invalid_user in invalid_users:
            with self.subTest(user=invalid_user):
                self.connection.search_strict.return_value = [
                    {"sAMAccountName": "valid-user"},
                    invalid_user,
                ]
                with self.assertRaises(ADMalformedResultError):
                    self.service.get_transitive_enabled_group_members("group")

    @patch.object(ADMembershipService, "resolve_group_dn")
    def test_strict_user_search_failure_propagates(self, mock_resolve):
        mock_resolve.return_value = ADGetResult.found_item(
            {"distinguishedName": "CN=Group,DC=example,DC=test"}
        )
        self.connection.search_strict.side_effect = ADTransportError()

        with self.assertRaises(ADTransportError):
            self.service.get_transitive_enabled_group_members("group")


class TestADMembershipIntegration(unittest.TestCase):
    """Exercise membership behavior through the real strict connection path."""

    def setUp(self):
        self.connection_patcher = patch("python_apis.apis.ad_api.Connection")
        self.connection_class = self.connection_patcher.start()
        self.addCleanup(self.connection_patcher.stop)
        self.ldap_connection = MagicMock()
        self.ldap_connection.bind.return_value = True
        self.ldap_connection.server.host = "directory.example.test"
        self.connection_class.return_value = self.ldap_connection
        self.ad_connection = ADConnection(
            ["ldaps://directory.example.test"],
            "DC=example,DC=test",
        )
        self.service = ADMembershipService(self.ad_connection)

    @staticmethod
    def _page(connection, entries, result_code=0):
        """Yield entries and set the final LDAP result when consumed."""

        def generator():
            yield from entries
            connection.result = {"result": result_code}

        return generator()

    def test_multi_page_membership_is_complete_unique_and_normalized(self):
        group_page = self._page(
            self.ldap_connection,
            [{"attributes": {"distinguishedName": "CN=Group,DC=example,DC=test"}}],
        )
        member_pages = self._page(
            self.ldap_connection,
            [
                {"attributes": {"sAMAccountName": "User-A"}},
                {"attributes": {"sAMAccountName": "USER-B"}},
                {"attributes": {"sAMAccountName": "user-a"}},
            ],
        )
        self.ldap_connection.extend.standard.paged_search.side_effect = [
            group_page,
            member_pages,
        ]

        result = self.service.get_transitive_enabled_group_members("stable-group")

        self.assertTrue(result.group_found)
        self.assertEqual(result.members, ("user-a", "user-b"))
        calls = self.ldap_connection.extend.standard.paged_search.call_args_list
        self.assertEqual(calls[0].kwargs["paged_size"], 500)
        self.assertEqual(calls[1].kwargs["paged_size"], 500)

    def test_each_refresh_resolves_the_group_current_dn(self):
        old_dn = "CN=Group,OU=Old,DC=example,DC=test"
        new_dn = "CN=Group,OU=New,DC=example,DC=test"
        self.ldap_connection.extend.standard.paged_search.side_effect = [
            self._page(
                self.ldap_connection,
                [{"attributes": {"distinguishedName": old_dn}}],
            ),
            self._page(self.ldap_connection, []),
            self._page(
                self.ldap_connection,
                [{"attributes": {"distinguishedName": new_dn}}],
            ),
            self._page(self.ldap_connection, []),
        ]

        self.service.get_transitive_enabled_group_members("stable-group")
        self.service.get_transitive_enabled_group_members("stable-group")

        calls = self.ldap_connection.extend.standard.paged_search.call_args_list
        self.assertIn("OU=Old", calls[1].kwargs["search_filter"])
        self.assertIn("OU=New", calls[3].kwargs["search_filter"])

    def test_partial_member_page_is_discarded_before_retry(self):
        recovered_connection = MagicMock()
        recovered_connection.bind.return_value = True
        recovered_connection.server.host = "directory-backup.example.test"

        def interrupted_members():
            yield {"attributes": {"sAMAccountName": "PARTIAL_MEMBER_CANARY"}}
            raise LDAPCommunicationError("TRANSPORT_CANARY")

        self.ldap_connection.extend.standard.paged_search.side_effect = [
            self._page(
                self.ldap_connection,
                [{"attributes": {"distinguishedName": "CN=Group,DC=example,DC=test"}}],
            ),
            interrupted_members(),
        ]
        recovered_connection.extend.standard.paged_search.return_value = self._page(
            recovered_connection,
            [{"attributes": {"sAMAccountName": "Complete-Member"}}],
        )
        self.connection_class.side_effect = [recovered_connection]

        result = self.service.get_transitive_enabled_group_members("stable-group")

        self.assertEqual(result.members, ("complete-member",))
        self.assertNotIn("partial_member_canary", result.members)
        self.assertEqual(self.ad_connection.last_retry_telemetry.retry_count, 1)
        self.assertTrue(self.ad_connection.last_retry_telemetry.recovered)

    def test_rejected_member_query_never_becomes_empty_success(self):
        self.ldap_connection.extend.standard.paged_search.side_effect = [
            self._page(
                self.ldap_connection,
                [{"attributes": {"distinguishedName": "CN=Group,DC=example,DC=test"}}],
            ),
            self._page(self.ldap_connection, [], result_code=50),
        ]

        with self.assertRaises(ADQueryRejectedError):
            self.service.get_transitive_enabled_group_members("stable-group")

    def test_exhausted_transport_never_becomes_empty_success(self):
        self.ldap_connection.extend.standard.paged_search.side_effect = [
            self._page(
                self.ldap_connection,
                [{"attributes": {"distinguishedName": "CN=Group,DC=example,DC=test"}}],
            ),
            LDAPCommunicationError("FIRST_TRANSPORT_CANARY"),
        ]
        recovered_connection = MagicMock()
        recovered_connection.bind.return_value = True
        recovered_connection.server.host = "directory-backup.example.test"
        recovered_connection.extend.standard.paged_search.side_effect = LDAPCommunicationError(
            "SECOND_TRANSPORT_CANARY"
        )
        self.connection_class.side_effect = [recovered_connection]

        with self.assertRaises(ADTransportError) as captured_error:
            self.service.get_transitive_enabled_group_members("stable-group")

        message = str(captured_error.exception)
        self.assertNotIn("FIRST_TRANSPORT_CANARY", message)
        self.assertNotIn("SECOND_TRANSPORT_CANARY", message)
        self.assertNotIn("stable-group", message)
        self.assertEqual(self.ad_connection.last_retry_telemetry.retry_count, 1)


if __name__ == "__main__":
    unittest.main()
