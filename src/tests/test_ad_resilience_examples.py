"""Tests for the resilient AD and OU inheritance examples."""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from examples import ad_resilient_search, ou_inheritance
from python_apis.apis import AD_RECOVERABLE_READ_EXCEPTIONS


def _printed_text(mock_print: MagicMock) -> str:
    """Join captured print arguments for safe-output assertions."""

    return "\n".join(
        " ".join(str(argument) for argument in call.args)
        for call in mock_print.call_args_list
    )


def _retry_telemetry() -> SimpleNamespace:
    """Build sanitized retry telemetry for example tests."""

    return SimpleNamespace(
        attempt_count=2,
        retry_count=1,
        recovered=False,
        failed_server="controller-deadbeef",
        selected_server="controller-cafebabe",
        elapsed_seconds=1.25,
    )


class TestResilientSearchExample(unittest.TestCase):
    """Validate exhausted reads produce masked aggregate output."""

    def test_exhausted_read_does_not_print_raw_exception(self):
        connection = MagicMock()
        connection.search.side_effect = AD_RECOVERABLE_READ_EXCEPTIONS[1](
            "ldap01.example.com connection refused"
        )
        connection.last_retry_telemetry = _retry_telemetry()

        with (
            patch.object(ad_resilient_search, "build_connection", return_value=connection),
            patch("builtins.print") as mock_print,
        ):
            ad_resilient_search.main()

        output = _printed_text(mock_print)
        self.assertIn("LDAP read failed", output)
        self.assertIn("controller-deadbeef", output)
        self.assertNotIn("ldap01.example.com", output)
        self.assertNotIn("connection refused", output)


class TestOUInheritanceExample(unittest.TestCase):
    """Validate fail-closed object reads and sanitized LDAP failures."""

    def test_read_objects_aborts_at_first_missing_ou(self):
        connection = MagicMock()
        connection.search.return_value = [
            {"ou": "OU=Users,DC=example,DC=com"},
            {"distinguishedName": "CN=No OU,DC=example,DC=com"},
        ]

        with self.assertRaises(ou_inheritance.DirectoryObjectReadError) as context:
            ou_inheritance.read_objects(connection)

        self.assertEqual(context.exception.entry_index, 1)

    def test_main_reports_missing_ou_index_without_reduced_success(self):
        connection = MagicMock()
        connection.search.return_value = [
            {"distinguishedName": "CN=No OU,DC=example,DC=com"},
        ]

        with (
            patch.object(ou_inheritance, "build_connection", return_value=connection),
            patch("builtins.print") as mock_print,
        ):
            ou_inheritance.main()

        output = _printed_text(mock_print)
        self.assertIn("entry_index=0", output)
        self.assertNotIn("Completed OU enrichment", output)

    def test_read_and_tree_failures_print_only_masked_telemetry(self):
        failure_cases = (
            ("read_objects", AD_RECOVERABLE_READ_EXCEPTIONS[1]("ldap01 raw detail")),
            ("enrich_objects", AD_RECOVERABLE_READ_EXCEPTIONS[0]("ldap02 raw detail")),
        )
        for failing_function, exception in failure_cases:
            with self.subTest(failing_function=failing_function):
                connection = MagicMock()
                connection.last_retry_telemetry = _retry_telemetry()
                patches = [
                    patch.object(ou_inheritance, "build_connection", return_value=connection),
                    patch.object(
                        ou_inheritance,
                        "read_objects",
                        return_value=[],
                    ),
                    patch.object(ou_inheritance, "enrich_objects"),
                    patch("builtins.print"),
                ]
                with (
                    patches[0],
                    patches[1] as mock_read_objects,
                    patches[2] as mock_enrich_objects,
                    patches[3] as mock_print,
                ):
                    if failing_function == "read_objects":
                        mock_read_objects.side_effect = exception
                    else:
                        mock_enrich_objects.side_effect = exception
                    ou_inheritance.main()

                output = _printed_text(mock_print)
                self.assertIn("LDAP read failed", output)
                self.assertIn("controller-deadbeef", output)
                self.assertNotIn("ldap01 raw detail", output)
                self.assertNotIn("ldap02 raw detail", output)


if __name__ == "__main__":
    unittest.main()
