"""Tests for the structured deprecation helper (issue #27)."""

import unittest
import warnings

from python_apis.deprecation import build_legacy_message, warn_legacy


class TestBuildLegacyMessage(unittest.TestCase):
    """Validate message composition."""

    def test_message_names_legacy_replacement_and_hint(self):
        message = build_legacy_message(
            "ADConnection.get",
            replacement="ADConnection.get_v2",
            migration_hint="Branch on result.found.",
        )
        self.assertIn("ADConnection.get", message)
        self.assertIn("ADConnection.get_v2", message)
        self.assertIn("Branch on result.found.", message)

    def test_message_includes_since_when_provided(self):
        message = build_legacy_message(
            "old",
            replacement="new",
            migration_hint="do it",
            since="#26",
        )
        self.assertIn("#26", message)

    def test_message_omits_since_marker_when_absent(self):
        message = build_legacy_message(
            "old",
            replacement="new",
            migration_hint="do it",
        )
        self.assertNotIn("since", message)


class TestWarnLegacy(unittest.TestCase):
    """Validate warning emission and returned message."""

    def test_warn_legacy_emits_deprecation_warning(self):
        with self.assertWarns(DeprecationWarning):
            warn_legacy(
                "old",
                replacement="new",
                migration_hint="do it",
            )

    def test_warn_legacy_returns_emitted_message(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            message = warn_legacy(
                "old",
                replacement="new",
                migration_hint="do it",
            )
        self.assertEqual(len(caught), 1)
        self.assertEqual(str(caught[0].message), message)

    def test_warn_legacy_respects_category(self):
        with self.assertWarns(FutureWarning):
            warn_legacy(
                "old",
                replacement="new",
                migration_hint="do it",
                category=FutureWarning,
            )


if __name__ == "__main__":
    unittest.main()
