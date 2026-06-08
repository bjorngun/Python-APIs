"""Tests for service-level default compatibility mode resolution."""

import os
import unittest
from unittest.mock import MagicMock

from python_apis.services import (
    ADGroupService,
    ADOrganizationalUnitService,
    ADUserService,
)
from python_apis.services.compatibility_mode import AD_COMPATIBILITY_ENV_VAR


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


if __name__ == "__main__":
    unittest.main()
