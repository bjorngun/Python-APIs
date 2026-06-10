# test_batch_read_v2.py
"""Contract tests for the partial-failure-aware batch read v2 APIs (issue #24)."""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, ConfigDict

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from python_apis.models import ADBatchItemFailure, ADBatchReadResult
from python_apis.services.batch_read import (
    build_batch_read_result,
    resolve_identity,
)
from python_apis.services.ad_user_service import ADUserService
from python_apis.services.ad_group_service import ADGroupService
from python_apis.services.ad_ou_service import ADOrganizationalUnitService


class _SampleSchema(BaseModel):
    """Minimal schema requiring a name and an integer age."""

    model_config = ConfigDict(extra="ignore")

    distinguishedName: str
    age: int


class _SampleModel:
    """Plain model factory capturing validated data."""

    def __init__(self, **data):
        self.data = data


class TestResolveIdentity(unittest.TestCase):

    def test_prefers_distinguished_name(self):
        record = {
            'distinguishedName': 'cn=a',
            'sAMAccountName': 'a',
        }
        self.assertEqual(resolve_identity(record), 'cn=a')

    def test_falls_back_to_account_name(self):
        record = {'sAMAccountName': 'a'}
        self.assertEqual(resolve_identity(record), 'a')

    def test_reduces_list_values(self):
        record = {'distinguishedName': ['cn=a', 'cn=b']}
        self.assertEqual(resolve_identity(record), 'cn=a')

    def test_returns_none_when_absent(self):
        self.assertIsNone(resolve_identity({'mail': 'x@y'}))

    def test_skips_empty_values(self):
        record = {'distinguishedName': '', 'sAMAccountName': 'a'}
        self.assertEqual(resolve_identity(record), 'a')


class TestBuildBatchReadResult(unittest.TestCase):

    def test_all_success(self):
        records = [
            {'distinguishedName': 'cn=a', 'age': 1},
            {'distinguishedName': 'cn=b', 'age': 2},
        ]
        result = build_batch_read_result(
            records, schema=_SampleSchema, model_factory=_SampleModel
        )
        self.assertIsInstance(result, ADBatchReadResult)
        self.assertEqual(len(result.returned_items), 2)
        self.assertEqual(result.failed_items, [])
        self.assertEqual(
            result.totals, {'requested': 2, 'returned': 2, 'failed': 0}
        )
        self.assertIsNone(result.continuation_state)

    def test_all_failure(self):
        records = [
            {'distinguishedName': 'cn=a', 'age': 'not-an-int'},
            {'sAMAccountName': 'b'},  # missing required distinguishedName
        ]
        result = build_batch_read_result(
            records, schema=_SampleSchema, model_factory=_SampleModel
        )
        self.assertEqual(result.returned_items, [])
        self.assertEqual(len(result.failed_items), 2)
        self.assertEqual(
            result.totals, {'requested': 2, 'returned': 0, 'failed': 2}
        )
        failure = result.failed_items[0]
        self.assertIsInstance(failure, ADBatchItemFailure)
        self.assertEqual(failure.identity, 'cn=a')
        self.assertEqual(failure.failure_classification, 'validation')
        self.assertEqual(failure.error_code, 'AD_VALIDATION_ERROR')
        self.assertTrue(failure.raw_validation_details)
        # Identity falls back to account name when DN is missing.
        self.assertEqual(result.failed_items[1].identity, 'b')

    def test_mixed_success_and_failure_no_silent_drop(self):
        records = [
            {'distinguishedName': 'cn=ok', 'age': 5},
            {'distinguishedName': 'cn=bad', 'age': 'x'},
        ]
        result = build_batch_read_result(
            records, schema=_SampleSchema, model_factory=_SampleModel
        )
        self.assertEqual(len(result.returned_items), 1)
        self.assertEqual(len(result.failed_items), 1)
        # Every input record is accounted for (never silently dropped).
        self.assertEqual(
            result.totals['returned'] + result.totals['failed'],
            result.totals['requested'],
        )

    def test_empty_input(self):
        result = build_batch_read_result(
            [], schema=_SampleSchema, model_factory=_SampleModel
        )
        self.assertEqual(result.returned_items, [])
        self.assertEqual(result.failed_items, [])
        self.assertEqual(
            result.totals, {'requested': 0, 'returned': 0, 'failed': 0}
        )

    def test_preprocess_applied_before_validation(self):
        records = [{'distinguishedName': 'cn=a'}]

        def _add_age(record):
            record['age'] = 7
            return record

        result = build_batch_read_result(
            records,
            schema=_SampleSchema,
            model_factory=_SampleModel,
            preprocess=_add_age,
        )
        self.assertEqual(len(result.returned_items), 1)
        self.assertEqual(result.returned_items[0].data['age'], 7)

    def test_to_dict_is_serializable(self):
        records = [
            {'distinguishedName': 'cn=ok', 'age': 5},
            {'distinguishedName': 'cn=bad', 'age': 'x'},
        ]
        result = build_batch_read_result(
            records, schema=_SampleSchema, model_factory=_SampleModel
        )
        payload = result.to_dict()
        self.assertEqual(
            set(payload.keys()),
            {'returned_items', 'failed_items', 'totals', 'continuation_state'},
        )
        self.assertEqual(payload['failed_items'][0]['error_code'], 'AD_VALIDATION_ERROR')


def _env_getenv(env):
    return lambda k, d=None: env.get(k, d)


class _ServiceV2TestBase(unittest.TestCase):
    env_vars = {
        'LDAP_SERVER_LIST': 'ldap://server1',
        'SEARCH_BASE': 'dc=example,dc=com',
    }

    def _patch_getenv(self):
        patcher = patch('os.getenv', side_effect=_env_getenv(self.env_vars))
        patcher.start()
        self.addCleanup(patcher.stop)


class TestGetUsersFromAdV2(_ServiceV2TestBase):

    @patch('python_apis.services.ad_user_service.ADUser.get_attribute_list',
           return_value=['attr1'])
    @patch('python_apis.services.ad_user_service.ADUserSchema')
    def test_returns_batch_envelope(self, mock_schema, _mock_attrs):
        self._patch_getenv()
        ad_conn = MagicMock()
        ad_conn.search.return_value = [
            {'sAMAccountName': 'u1', 'distinguishedName': 'dn1'},
            {'sAMAccountName': 'u2', 'distinguishedName': 'dn2'},
        ]
        mock_schema.side_effect = lambda **data: MagicMock(model_dump=lambda: data)
        service = ADUserService(ad_connection=ad_conn, sql_connection=MagicMock())

        result = service.get_users_from_ad_v2()

        self.assertIsInstance(result, ADBatchReadResult)
        self.assertEqual(len(result.returned_items), 2)
        self.assertEqual(result.totals['requested'], 2)
        ad_conn.search.assert_called_once_with('(objectClass=user)', ['attr1'])

    def test_existing_list_method_signature_unchanged(self):
        # get_users_from_ad still returns a list, not an envelope.
        self._patch_getenv()
        ad_conn = MagicMock()
        ad_conn.search.return_value = []
        service = ADUserService(ad_connection=ad_conn, sql_connection=MagicMock())
        self.assertIsInstance(service.get_users_from_ad(), list)


class TestGetGroupsFromAdV2(_ServiceV2TestBase):

    @patch('python_apis.services.ad_group_service.ADGroup.get_attribute_list',
           return_value=['attr1'])
    @patch('python_apis.services.ad_group_service.ADGroupSchema')
    def test_returns_batch_envelope_with_group_type_name(self, mock_schema, _mock_attrs):
        self._patch_getenv()
        ad_conn = MagicMock()
        ad_conn.search.return_value = [
            {'distinguishedName': 'dn1', 'groupType': -2147483646},
        ]
        captured = {}

        def _schema(**data):
            captured.update(data)
            return MagicMock(model_dump=lambda: data)

        mock_schema.side_effect = _schema
        service = ADGroupService(ad_connection=ad_conn, sql_connection=MagicMock())

        with patch.object(ADGroupService, 'set_group_type_name') as mock_set:
            result = service.get_groups_from_ad_v2()
            mock_set.assert_called_once()

        self.assertIsInstance(result, ADBatchReadResult)
        self.assertEqual(len(result.returned_items), 1)

    def test_existing_list_method_signature_unchanged(self):
        self._patch_getenv()
        ad_conn = MagicMock()
        ad_conn.search.return_value = []
        service = ADGroupService(ad_connection=ad_conn, sql_connection=MagicMock())
        self.assertIsInstance(service.get_groups_from_ad(), list)


class TestGetOusFromAdV2(_ServiceV2TestBase):

    @patch('python_apis.services.ad_ou_service.ADOrganizationalUnit.get_attribute_list',
           return_value=['attr1'])
    @patch('python_apis.services.ad_ou_service.ADOrganizationalUnitSchema')
    def test_returns_batch_envelope(self, mock_schema, _mock_attrs):
        self._patch_getenv()
        ad_conn = MagicMock()
        ad_conn.search.return_value = [
            {'distinguishedName': 'ou=a,dc=x'},
        ]
        mock_schema.side_effect = lambda **data: MagicMock(model_dump=lambda: data)
        service = ADOrganizationalUnitService(
            ad_connection=ad_conn, sql_connection=MagicMock()
        )

        result = service.get_ous_from_ad_v2()

        self.assertIsInstance(result, ADBatchReadResult)
        self.assertEqual(len(result.returned_items), 1)
        ad_conn.search.assert_called_once_with(
            '(objectClass=organizationalUnit)', ['attr1']
        )

    def test_existing_list_method_signature_unchanged(self):
        self._patch_getenv()
        ad_conn = MagicMock()
        ad_conn.search.return_value = []
        service = ADOrganizationalUnitService(
            ad_connection=ad_conn, sql_connection=MagicMock()
        )
        self.assertIsInstance(service.get_ous_from_ad(), list)


if __name__ == '__main__':
    unittest.main()
