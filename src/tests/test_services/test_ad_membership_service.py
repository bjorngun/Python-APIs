"""Tests for strict AD-only membership queries."""

import unittest
from unittest.mock import MagicMock, patch

from python_apis.apis import escape_filter_value
from python_apis.apis.ad_errors import ADMalformedQueryError, ADMalformedResultError
from python_apis.services import ADMembershipService


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


if __name__ == "__main__":
    unittest.main()
