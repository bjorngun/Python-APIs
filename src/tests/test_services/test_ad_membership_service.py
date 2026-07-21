"""Tests for strict AD-only membership queries."""

import unittest
from unittest.mock import MagicMock, patch

from python_apis.apis import escape_filter_value
from python_apis.apis.ad_errors import (
    ADMalformedQueryError,
    ADMalformedResultError,
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


if __name__ == "__main__":
    unittest.main()
