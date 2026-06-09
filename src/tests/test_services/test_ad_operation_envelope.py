"""Service-layer contract tests for the AD operation envelope.

Validates that wired write operations across `ADUserService`, `ADGroupService`
and `ADOrganizationalUnitService` honor the compatibility-mode contract:

- ``legacy`` mode preserves the pre-modernization dict shape unchanged.
- ``mixed`` mode emits an envelope with legacy mirror keys (``success``,
  ``result``, ``message``) plus modern envelope fields.
- ``strict`` mode emits the modern envelope and omits legacy mirror keys.
- Exception paths populate ``exception_type``/``exception_message``/``message``
  and set ``success=False``.
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from ldap3.core.exceptions import LDAPException

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from python_apis.services.ad_user_service import ADUserService
from python_apis.services.ad_group_service import ADGroupService
from python_apis.services.ad_ou_service import ADOrganizationalUnitService
from python_apis.models.ad_user import ADUser

# Modern envelope fields that must be present whenever an envelope is emitted.
ENVELOPE_FIELDS = (
    "success",
    "operation_kind",
    "ldap_result",
    "exception_type",
    "exception_message",
    "request_context",
    "retry_count",
    "retried",
    "error_code",
)


class TestUserServiceEnvelope(unittest.TestCase):
    """Envelope contract for `ADUserService.enable_user`."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.mock_sql_connection = MagicMock()

    def _service(self, mode):
        return ADUserService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode=mode,
        )

    def _user(self):
        user = MagicMock(spec=ADUser)
        user.distinguishedName = "CN=John,DC=example,DC=com"
        return user

    def test_legacy_mode_preserves_dict_unchanged(self):
        service = self._service("legacy")
        self.mock_ad_connection.enable_user.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.enable_user(self._user())

        self.assertEqual(result, {"success": True, "result": "ok"})

    def test_mixed_mode_emits_envelope_with_legacy_mirrors(self):
        service = self._service("mixed")
        self.mock_ad_connection.enable_user.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.enable_user(self._user())

        for field in ENVELOPE_FIELDS:
            self.assertIn(field, result)
        self.assertEqual(result["operation_kind"], "write")
        self.assertTrue(result["success"])
        # Legacy mirrors present and consistent with modern fields.
        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["ldap_result"], "ok")
        self.assertIn("message", result)
        self.assertEqual(
            result["request_context"].get("compatibility_mode"), "mixed"
        )

    def test_strict_mode_omits_legacy_mirror_keys(self):
        service = self._service("strict")
        self.mock_ad_connection.enable_user.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.enable_user(self._user())

        for field in ENVELOPE_FIELDS:
            self.assertIn(field, result)
        self.assertNotIn("result", result)
        self.assertNotIn("message", result)
        self.assertEqual(result["ldap_result"], "ok")

    def test_per_call_override_beats_service_default(self):
        service = self._service("legacy")
        self.mock_ad_connection.enable_user.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.enable_user(self._user(), compatibility_mode="mixed")

        self.assertEqual(result["operation_kind"], "write")
        self.assertEqual(result["ldap_result"], "ok")


class TestGroupServiceEnvelope(unittest.TestCase):
    """Envelope contract for `ADGroupService.modify_group`."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.mock_sql_connection = MagicMock()

    def _service(self, mode):
        return ADGroupService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode=mode,
        )

    def _group(self):
        group = MagicMock()
        group.distinguishedName = "CN=Team,DC=example,DC=com"
        group.description = "old"
        return group

    def test_legacy_mode_preserves_dict_unchanged(self):
        service = self._service("legacy")
        self.mock_ad_connection.modify.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.modify_group(
            self._group(), [("description", "new")]
        )

        self.assertEqual(
            result,
            {
                "success": True,
                "result": "ok",
                "changes": {"description": "old -> new"},
            },
        )

    def test_mixed_mode_preserves_changes_and_mirrors(self):
        service = self._service("mixed")
        self.mock_ad_connection.modify.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.modify_group(
            self._group(), [("description", "new")]
        )

        for field in ENVELOPE_FIELDS:
            self.assertIn(field, result)
        self.assertEqual(result["changes"], {"description": "old -> new"})
        self.assertEqual(result["result"], "ok")
        self.assertEqual(
            result["request_context"].get("changes"),
            {"description": "old -> new"},
        )

    def test_strict_mode_omits_legacy_mirrors_keeps_changes(self):
        service = self._service("strict")
        self.mock_ad_connection.modify.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.modify_group(
            self._group(), [("description", "new")]
        )

        self.assertNotIn("result", result)
        self.assertNotIn("message", result)
        self.assertEqual(result["changes"], {"description": "old -> new"})
        self.assertEqual(result["ldap_result"], "ok")

    def test_exception_path_populates_envelope(self):
        service = self._service("mixed")
        self.mock_ad_connection.modify.side_effect = LDAPException("boom")

        result = service.modify_group(
            self._group(), [("description", "new")]
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["exception_type"], "LDAPException")
        self.assertEqual(result["exception_message"], "boom")
        self.assertEqual(result["message"], "boom")


class TestOrganizationalUnitServiceEnvelope(unittest.TestCase):
    """Envelope contract for `ADOrganizationalUnitService.modify_ou`."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.mock_sql_connection = MagicMock()

    def _service(self, mode):
        return ADOrganizationalUnitService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode=mode,
        )

    def _ou(self):
        ou = MagicMock()
        ou.distinguishedName = "OU=Team,DC=example,DC=com"
        ou.description = "old"
        return ou

    def test_legacy_mode_preserves_dict_unchanged(self):
        service = self._service("legacy")
        self.mock_ad_connection.modify.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.modify_ou(self._ou(), [("description", "new")])

        self.assertEqual(
            result,
            {
                "success": True,
                "result": "ok",
                "changes": {"description": "old -> new"},
            },
        )

    def test_mixed_mode_preserves_changes_and_mirrors(self):
        service = self._service("mixed")
        self.mock_ad_connection.modify.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.modify_ou(self._ou(), [("description", "new")])

        for field in ENVELOPE_FIELDS:
            self.assertIn(field, result)
        self.assertEqual(result["changes"], {"description": "old -> new"})
        self.assertEqual(result["result"], "ok")

    def test_exception_path_populates_envelope(self):
        service = self._service("strict")
        self.mock_ad_connection.modify.side_effect = LDAPException("denied")

        result = service.modify_ou(self._ou(), [("description", "new")])

        self.assertFalse(result["success"])
        self.assertEqual(result["exception_type"], "LDAPException")
        self.assertEqual(result["exception_message"], "denied")
        self.assertNotIn("message", result)


if __name__ == "__main__":
    unittest.main()
