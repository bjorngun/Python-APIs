# test_ad_get_result.py
"""Contract tests for the AD single-object get_v2 result envelope (issue #26)."""

import sys
from pathlib import Path
import json
import unittest

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from python_apis.models import ADGetResult
from python_apis.models.ad_get import AD_NOT_FOUND_CODE


class TestADGetResultConstructors(unittest.TestCase):

    def test_found_item(self):
        item = {'sAMAccountName': 'jdoe', 'cn': 'John Doe'}
        result = ADGetResult.found_item(item)
        self.assertTrue(result.found)
        self.assertEqual(result.item, item)
        self.assertIsNone(result.not_found_reason)
        self.assertIsNone(result.error_code)

    def test_not_found_defaults_to_no_match(self):
        result = ADGetResult.not_found()
        self.assertFalse(result.found)
        self.assertIsNone(result.item)
        self.assertEqual(result.not_found_reason, 'no_match')
        self.assertEqual(result.error_code, AD_NOT_FOUND_CODE)

    def test_not_found_error_code_is_canonical(self):
        self.assertEqual(AD_NOT_FOUND_CODE, 'AD_NOT_FOUND')

    def test_not_found_error_code_mirrors_taxonomy(self):
        # The duplicated literal must stay in sync with the services taxonomy.
        from python_apis.services.error_taxonomy import AD_NOT_FOUND
        self.assertEqual(AD_NOT_FOUND_CODE, AD_NOT_FOUND)


class TestADGetResultShape(unittest.TestCase):

    def test_to_dict_found_is_json_serializable(self):
        result = ADGetResult.found_item({'cn': 'John Doe'})
        payload = result.to_dict()
        self.assertEqual(
            set(payload.keys()),
            {'found', 'item', 'not_found_reason', 'error_code'},
        )
        self.assertTrue(payload['found'])
        self.assertEqual(payload['item'], {'cn': 'John Doe'})
        json.dumps(payload)

    def test_to_dict_not_found_is_json_serializable(self):
        payload = ADGetResult.not_found().to_dict()
        self.assertFalse(payload['found'])
        self.assertIsNone(payload['item'])
        self.assertEqual(payload['not_found_reason'], 'no_match')
        self.assertEqual(payload['error_code'], 'AD_NOT_FOUND')
        json.dumps(payload)

    def test_extra_fields_forbidden(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ADGetResult(found=True, item={}, unexpected='x')


if __name__ == '__main__':
    unittest.main()
