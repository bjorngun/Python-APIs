# test_multivalue.py
"""Contract tests for the AD multivalue dual-form representation (issue #25)."""

import sys
from pathlib import Path
import unittest

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from python_apis.models import (
    ADMultiValue,
    ADMultiValueMetadata,
    normalize_multivalue,
)


class TestNormalizationRules(unittest.TestCase):

    def test_rule1_none_is_absent(self):
        mv = normalize_multivalue(None)
        self.assertEqual(mv.values, [])
        self.assertEqual(mv.metadata.source, 'absent')
        self.assertFalse(mv.metadata.normalized)
        self.assertEqual(mv.metadata.count, 0)
        self.assertIsNone(mv.raw)

    def test_rule2_empty_list(self):
        mv = normalize_multivalue([])
        self.assertEqual(mv.values, [])
        self.assertEqual(mv.metadata.source, 'list')
        self.assertTrue(mv.metadata.normalized)
        self.assertEqual(mv.metadata.count, 0)

    def test_rule3_list_strips_drops_empty_preserves_order_and_dupes(self):
        mv = normalize_multivalue(['  a ', 'b', None, '', 'a'])
        self.assertEqual(mv.values, ['a', 'b', 'a'])
        self.assertEqual(mv.metadata.source, 'list')
        self.assertTrue(mv.metadata.normalized)
        self.assertEqual(mv.metadata.count, 3)
        # Raw is preserved verbatim.
        self.assertEqual(mv.raw, ['  a ', 'b', None, '', 'a'])

    def test_rule3_list_of_ints(self):
        mv = normalize_multivalue([1, 2, 3])
        self.assertEqual(mv.values, ['1', '2', '3'])
        self.assertEqual(mv.metadata.source, 'list')

    def test_rule4_non_str_scalar(self):
        mv = normalize_multivalue(42)
        self.assertEqual(mv.values, ['42'])
        self.assertEqual(mv.metadata.source, 'scalar')
        self.assertTrue(mv.metadata.normalized)
        self.assertEqual(mv.metadata.count, 1)

    def test_rule5_delimited_string(self):
        mv = normalize_multivalue('a, b ,c,')
        self.assertEqual(mv.values, ['a', 'b', 'c'])
        self.assertEqual(mv.metadata.source, 'delimited_string')
        self.assertTrue(mv.metadata.normalized)
        self.assertEqual(mv.metadata.count, 3)

    def test_rule6_plain_string(self):
        mv = normalize_multivalue('  hello ')
        self.assertEqual(mv.values, ['hello'])
        self.assertEqual(mv.metadata.source, 'scalar')
        self.assertFalse(mv.metadata.normalized)
        self.assertEqual(mv.metadata.count, 1)

    def test_rule6_empty_string(self):
        mv = normalize_multivalue('   ')
        self.assertEqual(mv.values, [])
        self.assertEqual(mv.metadata.source, 'scalar')
        self.assertEqual(mv.metadata.count, 0)

    def test_custom_delimiter(self):
        mv = normalize_multivalue('a;b;c', delimiter=';')
        self.assertEqual(mv.values, ['a', 'b', 'c'])
        self.assertEqual(mv.metadata.source, 'delimited_string')
        self.assertEqual(mv.metadata.delimiter, ';')


class TestDeterminism(unittest.TestCase):

    def test_same_input_same_output(self):
        raw = ['x', ' y ', 'x']
        first = normalize_multivalue(raw).to_dict()
        second = normalize_multivalue(raw).to_dict()
        self.assertEqual(first, second)

    def test_renormalizing_values_is_idempotent(self):
        # Re-normalizing the already-normalized list yields the same values.
        mv = normalize_multivalue(['a', 'b', 'a'])
        again = normalize_multivalue(mv.values)
        self.assertEqual(again.values, mv.values)


class TestLegacyAccessor(unittest.TestCase):

    def test_as_legacy_string_default_delimiter(self):
        mv = normalize_multivalue(['a', 'b', 'c'])
        self.assertEqual(mv.as_legacy_string(), 'a,b,c')

    def test_as_legacy_string_matches_legacy_join(self):
        # The historic schema behavior was ','.join(map(str, value)).
        raw = ['a', 'b', 'c']
        legacy = ','.join(map(str, raw))
        self.assertEqual(normalize_multivalue(raw).as_legacy_string(), legacy)

    def test_as_legacy_string_custom_delimiter(self):
        mv = normalize_multivalue(['a', 'b'])
        self.assertEqual(mv.as_legacy_string(delimiter='|'), 'a|b')

    def test_as_legacy_string_uses_metadata_delimiter(self):
        mv = normalize_multivalue('a;b', delimiter=';')
        self.assertEqual(mv.as_legacy_string(), 'a;b')

    def test_empty_legacy_string(self):
        self.assertEqual(normalize_multivalue(None).as_legacy_string(), '')


class TestShapeInvariants(unittest.TestCase):

    def test_from_raw_classmethod(self):
        mv = ADMultiValue.from_raw(['a', 'b'])
        self.assertIsInstance(mv, ADMultiValue)
        self.assertEqual(mv.values, ['a', 'b'])

    def test_to_dict_is_serializable(self):
        mv = normalize_multivalue(['a', 'b'])
        payload = mv.to_dict()
        self.assertEqual(set(payload.keys()), {'raw', 'values', 'metadata'})
        self.assertEqual(
            set(payload['metadata'].keys()),
            {'source', 'normalized', 'count', 'delimiter'},
        )
        self.assertEqual(payload['values'], ['a', 'b'])

    def test_count_always_matches_values_length(self):
        for raw in (None, [], ['a'], ['a', 'b'], 'a,b,c', 'scalar', 7):
            mv = normalize_multivalue(raw)
            self.assertEqual(mv.metadata.count, len(mv.values))

    def test_metadata_model_standalone(self):
        meta = ADMultiValueMetadata(source='list', normalized=True, count=2)
        self.assertEqual(meta.delimiter, ',')
        self.assertEqual(meta.to_dict()['source'], 'list')


if __name__ == '__main__':
    unittest.main()
