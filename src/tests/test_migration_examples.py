"""Tests for the in-package migration examples (issue #27)."""

import unittest

from python_apis import migration_examples


class TestMigrationExamples(unittest.TestCase):
    """Validate that every example returns a non-empty snippet."""

    def test_all_examples_returns_non_empty_strings(self):
        examples = migration_examples.all_examples()
        self.assertTrue(examples)
        for name, snippet in examples.items():
            with self.subTest(example=name):
                self.assertIsInstance(snippet, str)
                self.assertTrue(snippet.strip())

    def test_each_example_function_returns_non_empty_string(self):
        for func in (
            migration_examples.legacy_get_to_get_v2,
            migration_examples.list_read_to_batch_v2,
            migration_examples.raw_multivalue_to_dual_form,
            migration_examples.error_handling_with_taxonomy,
        ):
            with self.subTest(func=func.__name__):
                self.assertTrue(func().strip())

    def test_all_in_dunder_all_are_exported(self):
        for name in migration_examples.__all__:
            self.assertTrue(hasattr(migration_examples, name))

    def test_get_v2_example_mentions_modern_api(self):
        self.assertIn("get_v2", migration_examples.legacy_get_to_get_v2())

    def test_print_all_runs_without_error(self):
        # Should not raise; output is not asserted here.
        migration_examples.print_all()


if __name__ == "__main__":
    unittest.main()
