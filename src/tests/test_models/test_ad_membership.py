"""Tests for typed strict AD membership results."""

import unittest

from pydantic import ValidationError

from python_apis.models import ADGroupMembersResult


class TestADGroupMembersResult(unittest.TestCase):
    """Verify deterministic membership and absence invariants."""

    def test_found_members_are_unique_and_sorted(self):
        result = ADGroupMembersResult.found(("user-b", "user-a", "user-b"))

        self.assertTrue(result.group_found)
        self.assertEqual(result.members, ("user-a", "user-b"))
        self.assertIsNone(result.not_found_reason)
        self.assertIsNone(result.error_code)

    def test_found_empty_is_explicit_success(self):
        result = ADGroupMembersResult.found(set())

        self.assertTrue(result.group_found)
        self.assertEqual(result.members, ())
        self.assertIsNone(result.error_code)

    def test_missing_group_has_deterministic_metadata(self):
        result = ADGroupMembersResult.not_found()

        self.assertFalse(result.group_found)
        self.assertEqual(result.members, ())
        self.assertEqual(result.not_found_reason, "group_not_found")
        self.assertEqual(result.error_code, "AD_NOT_FOUND")

    def test_rejects_non_normalized_members(self):
        for member in ("User-A", "", "Straße"):
            with self.subTest(member=member), self.assertRaises(ValidationError):
                ADGroupMembersResult.found({member})

    def test_rejects_contradictory_found_state(self):
        with self.assertRaises(ValidationError):
            ADGroupMembersResult(
                group_found=True,
                not_found_reason="group_not_found",
                error_code="AD_NOT_FOUND",
            )

    def test_rejects_contradictory_missing_state(self):
        invalid_payloads = (
            {"group_found": False},
            {
                "group_found": False,
                "members": ("user-a",),
                "not_found_reason": "group_not_found",
                "error_code": "AD_NOT_FOUND",
            },
            {
                "group_found": False,
                "not_found_reason": "group_not_found",
                "error_code": "AD_UNKNOWN",
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ADGroupMembersResult(**payload)

    def test_serialization_contains_no_directory_metadata(self):
        payload = ADGroupMembersResult.found({"user-a"}).model_dump()

        self.assertEqual(
            payload,
            {
                "group_found": True,
                "members": ("user-a",),
                "not_found_reason": None,
                "error_code": None,
            },
        )
        self.assertNotIn("distinguishedName", payload)
        self.assertNotIn("ldap_result", payload)


if __name__ == "__main__":
    unittest.main()
