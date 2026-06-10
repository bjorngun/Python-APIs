"""Service-layer contract tests for the AD operation envelope.

Validates that wired write operations across `ADUserService`, `ADGroupService`
and `ADOrganizationalUnitService` always emit a strict
:class:`ADOperationEnvelope` response:

- Modern envelope fields are present and ``operation_kind`` is ``write``.
- Legacy mirror keys (``result``, ``message``) are never present.
- Operation extras such as ``changes`` are preserved as top-level keys.
- Exception paths populate ``exception_type``/``exception_message`` and set
  ``success=False``.
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
        self.mock_ad_connection.last_retry_telemetry = None
        self.mock_sql_connection = MagicMock()

    def _service(self):
        return ADUserService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
        )

    def _user(self):
        user = MagicMock(spec=ADUser)
        user.distinguishedName = "CN=John,DC=example,DC=com"
        return user

    def test_strict_envelope_omits_legacy_mirror_keys(self):
        service = self._service()
        self.mock_ad_connection.enable_user.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.enable_user(self._user())

        for field in ENVELOPE_FIELDS:
            self.assertIn(field, result)
        self.assertEqual(result["operation_kind"], "write")
        self.assertTrue(result["success"])
        self.assertNotIn("result", result)
        self.assertNotIn("message", result)
        self.assertEqual(result["ldap_result"], "ok")


class TestGroupServiceEnvelope(unittest.TestCase):
    """Envelope contract for `ADGroupService.modify_group`."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.mock_ad_connection.last_retry_telemetry = None
        self.mock_sql_connection = MagicMock()

    def _service(self):
        return ADGroupService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
        )

    def _group(self):
        group = MagicMock()
        group.distinguishedName = "CN=Team,DC=example,DC=com"
        group.description = "old"
        return group

    def test_strict_envelope_omits_legacy_mirrors_keeps_changes(self):
        service = self._service()
        self.mock_ad_connection.modify.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.modify_group(
            self._group(), [("description", "new")]
        )

        for field in ENVELOPE_FIELDS:
            self.assertIn(field, result)
        self.assertNotIn("result", result)
        self.assertNotIn("message", result)
        self.assertEqual(result["changes"], {"description": "old -> new"})
        self.assertEqual(result["ldap_result"], "ok")
        self.assertEqual(
            result["request_context"].get("changes"),
            {"description": "old -> new"},
        )

    def test_exception_path_populates_envelope(self):
        service = self._service()
        self.mock_ad_connection.modify.side_effect = LDAPException("boom")

        result = service.modify_group(
            self._group(), [("description", "new")]
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["exception_type"], "LDAPException")
        self.assertEqual(result["exception_message"], "boom")
        self.assertNotIn("message", result)


class TestOrganizationalUnitServiceEnvelope(unittest.TestCase):
    """Envelope contract for `ADOrganizationalUnitService.modify_ou`."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.mock_ad_connection.last_retry_telemetry = None
        self.mock_sql_connection = MagicMock()

    def _service(self):
        return ADOrganizationalUnitService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
        )

    def _ou(self):
        ou = MagicMock()
        ou.distinguishedName = "OU=Team,DC=example,DC=com"
        ou.description = "old"
        return ou

    def test_strict_envelope_omits_legacy_mirrors_keeps_changes(self):
        service = self._service()
        self.mock_ad_connection.modify.return_value = {
            "success": True,
            "result": "ok",
        }

        result = service.modify_ou(self._ou(), [("description", "new")])

        for field in ENVELOPE_FIELDS:
            self.assertIn(field, result)
        self.assertNotIn("result", result)
        self.assertNotIn("message", result)
        self.assertEqual(result["changes"], {"description": "old -> new"})
        self.assertEqual(result["ldap_result"], "ok")

    def test_exception_path_populates_envelope(self):
        service = self._service()
        self.mock_ad_connection.modify.side_effect = LDAPException("denied")

        result = service.modify_ou(self._ou(), [("description", "new")])

        self.assertFalse(result["success"])
        self.assertEqual(result["exception_type"], "LDAPException")
        self.assertEqual(result["exception_message"], "denied")
        self.assertNotIn("message", result)


if __name__ == "__main__":
    unittest.main()
