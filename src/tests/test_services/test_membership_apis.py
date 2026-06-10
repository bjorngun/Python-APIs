"""Contract tests for AD membership APIs (issue #22).

Covers ``ADGroupService.get_user_direct_groups`` and
``ADGroupService.resolve_primary_group`` happy and edge paths.
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from python_apis.services.ad_group_service import ADGroupService
from python_apis.models.ad_group import ADGroup
from python_apis.models.ad_user import ADUser


def _group_dict(dn: str, name: str = 'Team') -> dict:
    """Build a minimal valid raw group record (passes ADGroupSchema)."""
    return {
        'distinguishedName': dn,
        'name': name,
        'instanceType': 4,
        'sAMAccountType': 268435456,
        'groupType': -2147483646,
        'objectSid': 'S-1-5-21-1-2-3-1105',
    }


class TestMembershipAPIs(unittest.TestCase):
    """Validate direct-group and primary-group resolution."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.mock_sql_connection = MagicMock()
        self.service = ADGroupService(
            ad_connection=self.mock_ad_connection,
            sql_connection=self.mock_sql_connection,
        )

    # --- get_user_direct_groups -------------------------------------------

    def test_direct_groups_happy_path_with_aduser(self):
        self.mock_ad_connection.search.return_value = [
            _group_dict('CN=Team A,DC=example,DC=com', 'Team A'),
            _group_dict('CN=Team B,DC=example,DC=com', 'Team B'),
        ]
        user = ADUser(distinguishedName='CN=John,DC=example,DC=com')

        groups = self.service.get_user_direct_groups(user)

        self.assertEqual(len(groups), 2)
        self.assertTrue(all(isinstance(g, ADGroup) for g in groups))
        self.assertEqual({g.name for g in groups}, {'Team A', 'Team B'})
        search_filter = self.mock_ad_connection.search.call_args[0][0]
        self.assertEqual(
            search_filter,
            '(&(objectClass=group)(member=CN=John,DC=example,DC=com))',
        )

    def test_direct_groups_accepts_dn_string(self):
        self.mock_ad_connection.search.return_value = [
            _group_dict('CN=Team A,DC=example,DC=com', 'Team A'),
        ]

        groups = self.service.get_user_direct_groups('CN=Jane,DC=example,DC=com')

        self.assertEqual(len(groups), 1)
        search_filter = self.mock_ad_connection.search.call_args[0][0]
        self.assertIn('(member=CN=Jane,DC=example,DC=com)', search_filter)

    def test_direct_groups_empty_returns_empty_list(self):
        self.mock_ad_connection.search.return_value = []

        groups = self.service.get_user_direct_groups('CN=Nobody,DC=example,DC=com')

        self.assertEqual(groups, [])

    def test_direct_groups_escapes_filter_value(self):
        self.mock_ad_connection.search.return_value = []

        self.service.get_user_direct_groups('CN=a(b)*,DC=example,DC=com')

        search_filter = self.mock_ad_connection.search.call_args[0][0]
        # Special chars must be escaped to prevent LDAP filter injection.
        self.assertIn(r'\28', search_filter)  # (
        self.assertIn(r'\29', search_filter)  # )
        self.assertIn(r'\2a', search_filter)  # *

    def test_direct_groups_missing_dn_returns_empty_without_search(self):
        user = ADUser(distinguishedName=None)

        groups = self.service.get_user_direct_groups(user)

        self.assertEqual(groups, [])
        self.mock_ad_connection.search.assert_not_called()

    # --- resolve_primary_group --------------------------------------------

    def test_primary_group_happy_path_with_aduser(self):
        self.mock_ad_connection.search.return_value = [
            _group_dict('CN=Domain Users,DC=example,DC=com', 'Domain Users'),
        ]
        user = ADUser(
            distinguishedName='CN=John,DC=example,DC=com',
            objectSid='S-1-5-21-1-2-3-1105',
            primaryGroupID='513',
        )

        group = self.service.resolve_primary_group(user)

        self.assertIsInstance(group, ADGroup)
        self.assertEqual(group.name, 'Domain Users')
        search_filter = self.mock_ad_connection.search.call_args[0][0]
        # primaryGroupToken is a constructed attribute and cannot be filtered;
        # the group SID is derived from the user's objectSid + primaryGroupID.
        self.assertEqual(
            search_filter,
            '(&(objectClass=group)(objectSid=S-1-5-21-1-2-3-513))',
        )

    def test_primary_group_missing_id_returns_none_without_search(self):
        user = ADUser(
            distinguishedName='CN=John,DC=example,DC=com',
            objectSid='S-1-5-21-1-2-3-1105',
            primaryGroupID=None,
        )

        group = self.service.resolve_primary_group(user)

        self.assertIsNone(group)
        self.mock_ad_connection.search.assert_not_called()

    def test_primary_group_missing_object_sid_returns_none_without_search(self):
        user = ADUser(
            distinguishedName='CN=John,DC=example,DC=com',
            objectSid=None,
            primaryGroupID='513',
        )

        group = self.service.resolve_primary_group(user)

        self.assertIsNone(group)
        self.mock_ad_connection.search.assert_not_called()

    def test_primary_group_escapes_filter_value(self):
        self.mock_ad_connection.search.return_value = []
        user = ADUser(
            distinguishedName='CN=John,DC=example,DC=com',
            objectSid='S-1-5-21-a(b)*-1105',
            primaryGroupID='513',
        )

        self.service.resolve_primary_group(user)

        search_filter = self.mock_ad_connection.search.call_args[0][0]
        # Derived SID values must be escaped to prevent LDAP filter injection.
        self.assertIn(r'\28', search_filter)  # (
        self.assertIn(r'\29', search_filter)  # )
        self.assertIn(r'\2a', search_filter)  # *

    def test_primary_group_no_match_returns_none(self):
        self.mock_ad_connection.search.return_value = []
        user = ADUser(
            distinguishedName='CN=John,DC=example,DC=com',
            objectSid='S-1-5-21-1-2-3-1105',
            primaryGroupID='999',
        )

        group = self.service.resolve_primary_group(user)

        self.assertIsNone(group)


if __name__ == '__main__':
    unittest.main()
