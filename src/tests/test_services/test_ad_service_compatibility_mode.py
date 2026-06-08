"""Tests for service-level default compatibility mode resolution."""

import os
import unittest
from unittest.mock import MagicMock, patch

from python_apis.services import (
    ADGroupService,
    ADOrganizationalUnitService,
    ADUserService,
)
from python_apis.services.compatibility_mode import AD_COMPATIBILITY_ENV_VAR
from python_apis.services.compatibility_mode import resolve_service_compatibility_mode


class TestServiceCompatibilityModeDefaults(unittest.TestCase):
    """Validate compatibility mode defaults across AD service constructors."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.mock_sql_connection = MagicMock()

    def tearDown(self):
        os.environ.pop(AD_COMPATIBILITY_ENV_VAR, None)

    def test_user_service_defaults_to_legacy(self):
        service = ADUserService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
        )

        self.assertEqual(service.compatibility_mode, "legacy")

    def test_user_service_uses_explicit_mode(self):
        service = ADUserService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="strict",
        )

        self.assertEqual(service.compatibility_mode, "strict")

    def test_group_service_uses_environment_mode(self):
        os.environ[AD_COMPATIBILITY_ENV_VAR] = "mixed"

        service = ADGroupService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
        )

        self.assertEqual(service.compatibility_mode, "mixed")

    def test_ou_service_invalid_mode_falls_back_to_legacy(self):
        service = ADOrganizationalUnitService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="invalid-mode",
        )

        self.assertEqual(service.compatibility_mode, "legacy")

    def test_service_supports_all_explicit_modes(self):
        for mode in ("legacy", "mixed", "strict"):
            with self.subTest(mode=mode):
                user_service = ADUserService(
                    ad_connection=self.mock_ad_connection,
                    sql_connection=self.mock_sql_connection,
                    compatibility_mode=mode,
                )
                group_service = ADGroupService(
                    ad_connection=self.mock_ad_connection,
                    sql_connection=self.mock_sql_connection,
                    compatibility_mode=mode,
                )
                ou_service = ADOrganizationalUnitService(
                    ad_connection=self.mock_ad_connection,
                    sql_connection=self.mock_sql_connection,
                    compatibility_mode=mode,
                )

                self.assertEqual(user_service.compatibility_mode, mode)
                self.assertEqual(group_service.compatibility_mode, mode)
                self.assertEqual(ou_service.compatibility_mode, mode)

    def test_per_call_override_precedence_helper(self):
        os.environ[AD_COMPATIBILITY_ENV_VAR] = "strict"

        service = ADUserService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="legacy",
        )

        effective_mode = resolve_service_compatibility_mode(
            per_call_mode="mixed",
            service_mode=service.compatibility_mode,
        )

        self.assertEqual(effective_mode, "mixed")

    def test_user_read_operation_accepts_per_call_override(self):
        service = ADUserService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="legacy",
        )
        self.mock_ad_connection.search.return_value = []

        with patch(
            "python_apis.services.ad_user_service.resolve_service_compatibility_mode",
            return_value="mixed",
        ) as mock_resolve:
            service.get_users_from_ad(compatibility_mode="mixed")

        mock_resolve.assert_called_with(per_call_mode="mixed", service_mode="legacy")

    def test_group_read_operation_accepts_per_call_override(self):
        service = ADGroupService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="legacy",
        )
        self.mock_ad_connection.search.return_value = []

        with patch(
            "python_apis.services.ad_group_service.resolve_service_compatibility_mode",
            return_value="mixed",
        ) as mock_resolve:
            service.get_groups_from_ad(compatibility_mode="mixed")

        mock_resolve.assert_called_with(per_call_mode="mixed", service_mode="legacy")

    def test_ou_read_operation_accepts_per_call_override(self):
        service = ADOrganizationalUnitService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="legacy",
        )
        self.mock_ad_connection.search.return_value = []

        with patch(
            "python_apis.services.ad_ou_service.resolve_service_compatibility_mode",
            return_value="mixed",
        ) as mock_resolve:
            service.get_ous_from_ad(compatibility_mode="mixed")

        mock_resolve.assert_called_with(per_call_mode="mixed", service_mode="legacy")

    def test_user_introspection_returns_default_and_effective_modes(self):
        service = ADUserService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="legacy",
        )

        introspection = service.get_compatibility_mode(compatibility_mode="strict")

        self.assertEqual(
            introspection,
            {"service_default_mode": "legacy", "effective_mode": "strict"},
        )

    def test_group_introspection_without_per_call_uses_service_default(self):
        service = ADGroupService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="mixed",
        )

        introspection = service.get_compatibility_mode()

        self.assertEqual(
            introspection,
            {"service_default_mode": "mixed", "effective_mode": "mixed"},
        )

    def test_ou_introspection_with_invalid_per_call_falls_back_to_legacy(self):
        service = ADOrganizationalUnitService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
            compatibility_mode="strict",
        )

        introspection = service.get_compatibility_mode(compatibility_mode="bad")

        self.assertEqual(
            introspection,
            {"service_default_mode": "strict", "effective_mode": "legacy"},
        )


if __name__ == "__main__":
    unittest.main()
