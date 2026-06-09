"""Contract tests for typed, dict-compatible AD response models.

These tests pin stable field names and types and verify that the typed models
preserve legacy dictionary access and JSON serializability.
"""

import json
import unittest
from collections import defaultdict

from python_apis.models import (
    ADEntry,
    ADOperationEnvelope,
    ADOperationResponse,
    ADResponse,
    ADSearchResponse,
)


class TestADOperationResponse(unittest.TestCase):
    """Validate the mutation envelope contract and dict-compatibility."""

    def setUp(self):
        self.legacy = {
            "result": {"description": "success", "result": 0},
            "success": True,
        }
        self.response = ADOperationResponse.from_legacy(self.legacy)

    def test_typed_attribute_access(self):
        self.assertIs(self.response.success, True)
        self.assertEqual(self.response.result, {"description": "success", "result": 0})

    def test_field_types_are_stable(self):
        self.assertIsInstance(self.response.success, bool)
        self.assertIsInstance(self.response.result, dict)

    def test_legacy_key_access_parity(self):
        self.assertEqual(self.response["success"], self.response.success)
        self.assertEqual(self.response["result"], self.response.result)
        self.assertIn("success", self.response)
        self.assertIn("result", self.response)
        self.assertEqual(self.response.get("missing", "fallback"), "fallback")

    def test_mapping_unpacking_and_dict_conversion(self):
        self.assertEqual(dict(self.response), {**self.response})
        self.assertEqual(set(self.response.keys()), {"success", "result"})

    def test_lossless_round_trip(self):
        self.assertEqual(self.response.to_dict(), self.legacy)

    def test_preserves_unknown_keys(self):
        response = ADOperationResponse.from_legacy(
            {"result": {}, "success": False, "extra": 42}
        )
        self.assertEqual(response["extra"], 42)
        self.assertIn("extra", response)

    def test_json_serializable(self):
        payload = json.loads(self.response.model_dump_json())
        self.assertEqual(payload, self.legacy)

    def test_string_result_is_preserved(self):
        # AD service error paths return {'success': False, 'result': str(e)}.
        legacy = {"success": False, "result": "LDAP error"}
        response = ADOperationResponse.from_legacy(legacy)

        self.assertEqual(response.result, "LDAP error")
        self.assertEqual(response["result"], "LDAP error")
        self.assertEqual(response.to_dict(), legacy)


class TestADEntry(unittest.TestCase):
    """Validate the single-object read model contract."""

    def setUp(self):
        self.legacy = {"cn": "jon", "department": "IT", "ou": "OU=Users,DC=example"}
        self.entry = ADEntry.from_legacy(self.legacy)

    def test_is_ad_response(self):
        self.assertIsInstance(self.entry, ADResponse)

    def test_dict_compatible_access(self):
        self.assertEqual(self.entry["cn"], "jon")
        self.assertEqual(self.entry.get("department"), "IT")
        self.assertIn("ou", self.entry)
        self.assertEqual(dict(self.entry), self.legacy)

    def test_missing_key_raises(self):
        with self.assertRaises(KeyError):
            _ = self.entry["does_not_exist"]

    def test_preserves_defaultdict_no_result_behavior(self):
        # ADConnection.get() returns defaultdict(lambda: '') on no match;
        # missing-key indexing must keep returning the legacy empty string.
        empty_get = defaultdict(lambda: "")
        entry = ADEntry.from_legacy(empty_get)

        self.assertEqual(entry["cn"], "")
        self.assertEqual(entry["anything"], "")

    def test_lossless_round_trip(self):
        self.assertEqual(self.entry.to_dict(), self.legacy)

    def test_json_serializable(self):
        self.assertEqual(json.loads(self.entry.model_dump_json()), self.legacy)


class TestADSearchResponse(unittest.TestCase):
    """Validate the multi-object read wrapper contract."""

    def setUp(self):
        self.legacy = [
            {"cn": "alice", "sAMAccountName": "alice"},
            {"cn": "bob", "sAMAccountName": "bob", "extra": 1},
        ]
        self.search = ADSearchResponse.from_legacy(self.legacy)

    def test_list_compatible_access(self):
        self.assertEqual(len(self.search), 2)
        self.assertEqual(self.search[0]["cn"], "alice")
        self.assertEqual([entry["cn"] for entry in self.search], ["alice", "bob"])

    def test_entries_are_typed(self):
        self.assertTrue(all(isinstance(entry, ADEntry) for entry in self.search))

    def test_lossless_round_trip(self):
        self.assertEqual(self.search.to_list(), self.legacy)

    def test_empty_search_default(self):
        empty = ADSearchResponse()
        self.assertEqual(len(empty), 0)
        self.assertEqual(empty.to_list(), [])


class TestADOperationEnvelope(unittest.TestCase):
    """Validate the operation envelope model, builder, and mode-aware output."""

    def test_required_fields_and_defaults(self):
        envelope = ADOperationEnvelope(success=True, operation_kind="write")

        self.assertIs(envelope.success, True)
        self.assertEqual(envelope.operation_kind, "write")
        self.assertIsNone(envelope.ldap_result)
        self.assertIsNone(envelope.exception_type)
        self.assertIsNone(envelope.exception_message)
        self.assertEqual(envelope.request_context, {})
        self.assertEqual(envelope.retry_count, 0)
        self.assertIs(envelope.retried, False)
        self.assertIsNone(envelope.error_code)

    def test_legacy_mirrors_match_modern_fields(self):
        envelope = ADOperationEnvelope(
            success=True,
            operation_kind="write",
            ldap_result={"description": "success"},
            exception_message="none",
        )

        # Mirrors readable via attribute and Mapping access.
        self.assertEqual(envelope.result, envelope.ldap_result)
        self.assertEqual(envelope.message, envelope.exception_message)
        self.assertEqual(envelope["result"], envelope.ldap_result)
        self.assertEqual(envelope["message"], envelope.exception_message)

    def test_json_serializable(self):
        envelope = ADOperationEnvelope(
            success=True,
            operation_kind="write",
            ldap_result={"description": "success"},
        )
        payload = json.loads(envelope.model_dump_json())

        self.assertEqual(payload["result"], {"description": "success"})
        self.assertEqual(payload["ldap_result"], {"description": "success"})

    def test_from_operation_success(self):
        envelope = ADOperationEnvelope.from_operation(
            operation_kind="write",
            ldap_result={"description": "success"},
            request_context={"dn": "CN=x"},
        )

        self.assertIs(envelope.success, True)
        self.assertIsNone(envelope.exception_type)
        self.assertEqual(envelope.ldap_result, {"description": "success"})
        self.assertEqual(envelope.request_context, {"dn": "CN=x"})

    def test_from_operation_exception_capture(self):
        envelope = ADOperationEnvelope.from_operation(
            operation_kind="write",
            exception=ValueError("boom"),
        )

        self.assertIs(envelope.success, False)
        self.assertEqual(envelope.exception_type, "ValueError")
        self.assertEqual(envelope.exception_message, "boom")
        self.assertEqual(envelope.message, "boom")

    def test_from_operation_explicit_success_overrides_default(self):
        envelope = ADOperationEnvelope.from_operation(
            operation_kind="write",
            success=False,
            ldap_result="partial",
        )

        self.assertIs(envelope.success, False)

    def test_to_response_legacy_includes_mirrors(self):
        envelope = ADOperationEnvelope.from_operation(
            operation_kind="write",
            ldap_result={"description": "success"},
        )
        payload = envelope.to_response("legacy")

        self.assertIn("result", payload)
        self.assertIn("message", payload)
        self.assertEqual(payload["result"], payload["ldap_result"])

    def test_to_response_mixed_includes_mirrors(self):
        envelope = ADOperationEnvelope.from_operation(operation_kind="write")
        payload = envelope.to_response("mixed")

        self.assertIn("result", payload)
        self.assertIn("message", payload)

    def test_to_response_strict_omits_mirrors(self):
        envelope = ADOperationEnvelope.from_operation(
            operation_kind="write",
            ldap_result={"description": "success"},
        )
        payload = envelope.to_response("strict")

        self.assertNotIn("result", payload)
        self.assertNotIn("message", payload)
        self.assertIn("ldap_result", payload)
        self.assertIn("success", payload)

    def test_to_response_unknown_mode_falls_back_to_legacy(self):
        envelope = ADOperationEnvelope.from_operation(operation_kind="write")
        payload = envelope.to_response("nonsense")

        self.assertIn("result", payload)
        self.assertIn("message", payload)


if __name__ == "__main__":
    unittest.main()
