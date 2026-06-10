"""Tests for the in-package discovery toolkit (issue #27)."""

import importlib
import unittest

from python_apis import discovery


def _resolve_entry_point(entry_point: str):
    """Import ``module:dotted.attr`` and return the resolved object."""

    module_path, _, attr_path = entry_point.partition(":")
    obj = importlib.import_module(module_path)
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj


class TestCapabilityRegistry(unittest.TestCase):
    """Validate the capability registry shape and entry-point integrity."""

    def test_list_capabilities_returns_dicts_with_expected_keys(self):
        capabilities = discovery.list_capabilities()
        self.assertGreater(len(capabilities), 0)
        expected_keys = {
            "name",
            "summary",
            "since_issue",
            "entry_points",
            "legacy",
            "migration",
            "example",
        }
        for capability in capabilities:
            self.assertEqual(set(capability), expected_keys)
            self.assertIsInstance(capability["name"], str)
            self.assertIsInstance(capability["entry_points"], list)
            self.assertTrue(capability["entry_points"])

    def test_capability_names_are_unique(self):
        names = [cap["name"] for cap in discovery.list_capabilities()]
        self.assertEqual(len(names), len(set(names)))

    def test_every_entry_point_is_importable(self):
        for capability in discovery.list_capabilities():
            for entry_point in capability["entry_points"]:
                with self.subTest(entry_point=entry_point):
                    self.assertIsNotNone(_resolve_entry_point(entry_point))

    def test_legacy_entry_points_are_importable_when_present(self):
        for capability in discovery.list_capabilities():
            legacy = capability["legacy"]
            if legacy and ":" in legacy:
                with self.subTest(legacy=legacy):
                    self.assertIsNotNone(_resolve_entry_point(legacy))

    def test_get_capability_returns_matching_record(self):
        record = discovery.get_capability("get-v2")
        self.assertEqual(record["name"], "get-v2")
        self.assertEqual(record["since_issue"], 26)

    def test_get_capability_unknown_name_raises_keyerror_with_options(self):
        with self.assertRaises(KeyError) as ctx:
            discovery.get_capability("does-not-exist")
        self.assertIn("Available:", str(ctx.exception))


class TestCompatibilityModeIntrospection(unittest.TestCase):
    """Validate mode introspection helpers."""

    def test_active_compatibility_mode_returns_known_mode(self):
        mode = discovery.active_compatibility_mode()
        self.assertIn(mode, ("legacy", "mixed", "strict"))

    def test_active_compatibility_mode_honors_per_call_override(self):
        self.assertEqual(
            discovery.active_compatibility_mode(per_call_mode="strict"),
            "strict",
        )

    def test_describe_compatibility_modes_shape(self):
        described = discovery.describe_compatibility_modes()
        self.assertIn("env_var", described)
        self.assertIn("default_mode", described)
        self.assertIn("active_mode", described)
        self.assertEqual(
            set(described["modes"]),
            {"legacy", "mixed", "strict"},
        )


class TestQuickReference(unittest.TestCase):
    """Validate the printable quick reference."""

    def test_quick_reference_is_non_empty_and_mentions_capabilities(self):
        text = discovery.quick_reference()
        self.assertTrue(text.strip())
        for capability in discovery.list_capabilities():
            self.assertIn(capability["name"], text)


if __name__ == "__main__":
    unittest.main()
