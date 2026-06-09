"""Tests for service-layer compatibility mode resolver utilities."""

import os
import unittest

from python_apis.services.compatibility_mode import (
    AD_COMPATIBILITY_ENV_VAR,
    AD_DEFAULT_COMPATIBILITY_MODE,
    resolve_service_compatibility_mode,
)


class TestCompatibilityModeUtility(unittest.TestCase):
    """Validate deterministic AD compatibility mode resolution behavior."""

    def setUp(self):
        self.original_env_value = os.environ.get(AD_COMPATIBILITY_ENV_VAR)

    def tearDown(self):
        if self.original_env_value is None:
            os.environ.pop(AD_COMPATIBILITY_ENV_VAR, None)
            return
        os.environ[AD_COMPATIBILITY_ENV_VAR] = self.original_env_value

    def test_resolves_per_call_mode_first(self):
        os.environ[AD_COMPATIBILITY_ENV_VAR] = "strict"

        result = resolve_service_compatibility_mode(
            per_call_mode="mixed",
            service_mode="legacy",
        )

        self.assertEqual(result, "mixed")

    def test_resolves_service_mode_when_per_call_missing(self):
        os.environ[AD_COMPATIBILITY_ENV_VAR] = "strict"

        result = resolve_service_compatibility_mode(service_mode="mixed")

        self.assertEqual(result, "mixed")

    def test_resolves_environment_mode_when_no_explicit_modes(self):
        os.environ[AD_COMPATIBILITY_ENV_VAR] = "strict"

        result = resolve_service_compatibility_mode()

        self.assertEqual(result, "strict")

    def test_falls_back_to_legacy_for_invalid_mode(self):
        result = resolve_service_compatibility_mode(per_call_mode="invalid")

        self.assertEqual(result, AD_DEFAULT_COMPATIBILITY_MODE)

    def test_falls_back_to_legacy_for_empty_modes(self):
        os.environ[AD_COMPATIBILITY_ENV_VAR] = "   "

        result = resolve_service_compatibility_mode(
            per_call_mode="",
            service_mode="  ",
        )

        self.assertEqual(result, AD_DEFAULT_COMPATIBILITY_MODE)


if __name__ == "__main__":
    unittest.main()
