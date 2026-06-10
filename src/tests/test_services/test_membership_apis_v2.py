"""Contract tests for AD membership APIs v2 (issue #23).

Covers ``ADGroupService.get_user_transitive_groups`` and
``ADGroupService.get_group_members`` (paging + ranged retrieval), plus the
``ADConnection`` ranged-attribute retrieval that backs group member reads.
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from python_apis.apis.ad_api import ADConnection
from python_apis.services.ad_group_service import (
    ADGroupService,
    LDAP_MATCHING_RULE_IN_CHAIN,
)
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


class TestTransitiveGroups(unittest.TestCase):
    """Validate nested (transitive) group resolution."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.service = ADGroupService(
            ad_connection=self.mock_ad_connection,
            sql_connection=MagicMock(),
        )

    def test_transitive_groups_happy_path_uses_in_chain_rule(self):
        self.mock_ad_connection.search.return_value = [
            _group_dict('CN=Team A,DC=example,DC=com', 'Team A'),
        ]
        user = ADUser(distinguishedName='CN=John,DC=example,DC=com')

        groups = self.service.get_user_transitive_groups(user)

        self.assertEqual(len(groups), 1)
        self.assertTrue(all(isinstance(g, ADGroup) for g in groups))
        search_filter = self.mock_ad_connection.search.call_args[0][0]
        self.assertEqual(
            search_filter,
            f"(&(objectClass=group)(member:{LDAP_MATCHING_RULE_IN_CHAIN}:="
            "CN=John,DC=example,DC=com))",
        )

    def test_transitive_groups_accepts_dn_string(self):
        self.mock_ad_connection.search.return_value = [
            _group_dict('CN=Team A,DC=example,DC=com', 'Team A'),
        ]

        groups = self.service.get_user_transitive_groups('CN=Jane,DC=example,DC=com')

        self.assertEqual(len(groups), 1)
        search_filter = self.mock_ad_connection.search.call_args[0][0]
        self.assertIn(f"(member:{LDAP_MATCHING_RULE_IN_CHAIN}:=CN=Jane,DC=example,DC=com)",
                      search_filter)

    def test_transitive_groups_results_sorted_by_dn(self):
        self.mock_ad_connection.search.return_value = [
            _group_dict('CN=Zeta,DC=example,DC=com', 'Zeta'),
            _group_dict('CN=Alpha,DC=example,DC=com', 'Alpha'),
            _group_dict('CN=Mu,DC=example,DC=com', 'Mu'),
        ]
        user = ADUser(distinguishedName='CN=John,DC=example,DC=com')

        groups = self.service.get_user_transitive_groups(user)

        self.assertEqual(
            [g.distinguishedName for g in groups],
            [
                'CN=Alpha,DC=example,DC=com',
                'CN=Mu,DC=example,DC=com',
                'CN=Zeta,DC=example,DC=com',
            ],
        )

    def test_transitive_groups_escapes_filter_value(self):
        self.mock_ad_connection.search.return_value = []

        self.service.get_user_transitive_groups('CN=a(b)*,DC=example,DC=com')

        search_filter = self.mock_ad_connection.search.call_args[0][0]
        self.assertIn(r'\28', search_filter)  # (
        self.assertIn(r'\29', search_filter)  # )
        self.assertIn(r'\2a', search_filter)  # *

    def test_transitive_groups_missing_dn_returns_empty_without_search(self):
        groups = self.service.get_user_transitive_groups(ADUser(distinguishedName=None))

        self.assertEqual(groups, [])
        self.mock_ad_connection.search.assert_not_called()


class TestGroupMembers(unittest.TestCase):
    """Validate paged group member retrieval."""

    def setUp(self):
        self.mock_ad_connection = MagicMock()
        self.service = ADGroupService(
            ad_connection=self.mock_ad_connection,
            sql_connection=MagicMock(),
        )

    def _set_members(self, count: int):
        members = [f'CN=User{i:04d},DC=example,DC=com' for i in range(count)]
        self.mock_ad_connection.get_ranged_attribute.return_value = members
        return members

    def test_members_happy_path_single_page(self):
        members = self._set_members(3)

        page = self.service.get_group_members('CN=Team,DC=example,DC=com')

        self.assertEqual(page.members, members)
        self.assertEqual(page.total_count, 3)
        self.assertFalse(page.truncated)
        self.assertFalse(page.page_info['has_next_page'])
        self.assertIsNone(page.page_info['next_offset'])
        # Reads the group's member attribute via ranged retrieval.
        self.mock_ad_connection.get_ranged_attribute.assert_called_once_with(
            'CN=Team,DC=example,DC=com', 'member', limit=None
        )

    def test_members_accepts_adgroup_instance(self):
        self._set_members(2)
        group = ADGroup(distinguishedName='CN=Team,DC=example,DC=com', name='Team')

        page = self.service.get_group_members(group)

        self.assertEqual(page.total_count, 2)
        self.mock_ad_connection.get_ranged_attribute.assert_called_once_with(
            'CN=Team,DC=example,DC=com', 'member', limit=None
        )

    def test_members_paging_returns_requested_slice(self):
        members = self._set_members(10)

        page = self.service.get_group_members(
            'CN=Team,DC=example,DC=com', page_size=4, offset=4
        )

        self.assertEqual(page.members, members[4:8])
        self.assertEqual(page.total_count, 10)
        self.assertEqual(page.page_info['offset'], 4)
        self.assertEqual(page.page_info['page_size'], 4)
        self.assertEqual(page.page_info['next_offset'], 8)
        self.assertTrue(page.page_info['has_next_page'])

    def test_members_last_page_has_no_next(self):
        members = self._set_members(10)

        page = self.service.get_group_members(
            'CN=Team,DC=example,DC=com', page_size=4, offset=8
        )

        self.assertEqual(page.members, members[8:10])
        self.assertFalse(page.page_info['has_next_page'])
        self.assertIsNone(page.page_info['next_offset'])

    def test_members_non_positive_page_size_returns_all_from_offset(self):
        members = self._set_members(5)

        page = self.service.get_group_members(
            'CN=Team,DC=example,DC=com', page_size=0, offset=2
        )

        self.assertEqual(page.members, members[2:])
        self.assertFalse(page.page_info['has_next_page'])

    def test_members_truncated_when_max_members_exceeded(self):
        self._set_members(10)

        page = self.service.get_group_members(
            'CN=Team,DC=example,DC=com', page_size=50, max_members=3
        )

        self.assertTrue(page.truncated)
        self.assertEqual(page.total_count, 3)
        self.assertEqual(len(page.members), 3)

    def test_members_max_members_bounds_the_ranged_read(self):
        self._set_members(10)

        self.service.get_group_members(
            'CN=Team,DC=example,DC=com', page_size=50, max_members=3
        )

        # The cap is pushed into the ranged read (one past the cap so truncation
        # can still be detected) rather than fetching the whole membership.
        self.mock_ad_connection.get_ranged_attribute.assert_called_once_with(
            'CN=Team,DC=example,DC=com', 'member', limit=4
        )

    def test_members_no_cap_reads_every_range(self):
        self._set_members(5)

        self.service.get_group_members('CN=Team,DC=example,DC=com')

        self.mock_ad_connection.get_ranged_attribute.assert_called_once_with(
            'CN=Team,DC=example,DC=com', 'member', limit=None
        )

    def test_members_offset_beyond_total_returns_empty_page(self):
        self._set_members(3)

        page = self.service.get_group_members(
            'CN=Team,DC=example,DC=com', page_size=5, offset=99
        )

        self.assertEqual(page.members, [])
        self.assertEqual(page.total_count, 3)
        self.assertFalse(page.page_info['has_next_page'])

    def test_members_missing_dn_returns_empty_page_without_read(self):
        page = self.service.get_group_members(ADGroup(distinguishedName=None, name='X'))

        self.assertEqual(page.members, [])
        self.assertEqual(page.total_count, 0)
        self.assertFalse(page.truncated)
        self.mock_ad_connection.get_ranged_attribute.assert_not_called()

    def test_members_missing_dn_page_info_is_consistently_shaped(self):
        page = self.service.get_group_members(
            ADGroup(distinguishedName=None, name='X'), page_size=25
        )

        # Paging callers must find the same keys here as on populated pages.
        self.assertEqual(
            set(page.page_info),
            {'page_size', 'offset', 'next_offset', 'has_next_page'},
        )
        self.assertEqual(page.page_info['page_size'], 25)
        self.assertEqual(page.page_info['offset'], 0)
        self.assertIsNone(page.page_info['next_offset'])
        self.assertFalse(page.page_info['has_next_page'])


class TestRangedAttributeRetrieval(unittest.TestCase):
    """Validate ADConnection LDAP ranged attribute assembly."""

    def setUp(self):
        # Build an ADConnection without establishing a real LDAP session.
        self.connection = ADConnection.__new__(ADConnection)
        self.connection.connection = MagicMock()
        self.connection._last_retry_telemetry = None  # pylint: disable=protected-access

    def _stub_ranges(self, range_responses):
        """Make connection.search yield the given range responses in order."""
        state = {'index': 0}

        def search_side_effect(**_kwargs):
            attributes = range_responses[state['index']]
            self.connection.connection.response = [{'attributes': attributes}]
            state['index'] += 1
            return True

        self.connection.connection.search.side_effect = search_side_effect

    def test_parse_ranged_attribute_plain_key_is_terminal(self):
        values, nxt = ADConnection._parse_ranged_attribute(  # pylint: disable=protected-access
            {'member': ['CN=a', 'CN=b']}, 'member'
        )
        self.assertEqual(values, ['CN=a', 'CN=b'])
        self.assertIsNone(nxt)

    def test_parse_ranged_attribute_non_terminal_returns_next_start(self):
        values, nxt = ADConnection._parse_ranged_attribute(  # pylint: disable=protected-access
            {'member;range=0-1': ['CN=a', 'CN=b']}, 'member'
        )
        self.assertEqual(values, ['CN=a', 'CN=b'])
        self.assertEqual(nxt, 2)

    def test_parse_ranged_attribute_terminal_star(self):
        values, nxt = ADConnection._parse_ranged_attribute(  # pylint: disable=protected-access
            {'member;range=2-*': ['CN=c']}, 'member'
        )
        self.assertEqual(values, ['CN=c'])
        self.assertIsNone(nxt)

    def test_parse_ranged_attribute_missing_attribute(self):
        values, nxt = ADConnection._parse_ranged_attribute(  # pylint: disable=protected-access
            {'cn': ['Team']}, 'member'
        )
        self.assertEqual(values, [])
        self.assertIsNone(nxt)

    def test_parse_ranged_attribute_skips_empty_echo(self):
        # AD can echo the requested range back empty alongside the real range.
        values, nxt = ADConnection._parse_ranged_attribute(  # pylint: disable=protected-access
            {'member;range=0-*': [], 'member;range=0-1': ['CN=a', 'CN=b']}, 'member'
        )
        self.assertEqual(values, ['CN=a', 'CN=b'])
        self.assertEqual(nxt, 2)

    def test_get_ranged_attribute_assembles_multiple_ranges(self):
        self._stub_ranges([
            {'member;range=0-1': ['CN=a', 'CN=b']},
            {'member;range=2-3': ['CN=c', 'CN=d']},
            {'member;range=4-*': ['CN=e']},
        ])

        values = self.connection.get_ranged_attribute('CN=Team,DC=example,DC=com', 'member')

        self.assertEqual(values, ['CN=a', 'CN=b', 'CN=c', 'CN=d', 'CN=e'])
        self.assertEqual(self.connection.connection.search.call_count, 3)

    def test_get_ranged_attribute_single_range(self):
        self._stub_ranges([
            {'member;range=0-*': ['CN=a', 'CN=b']},
        ])

        values = self.connection.get_ranged_attribute('CN=Team,DC=example,DC=com', 'member')

        self.assertEqual(values, ['CN=a', 'CN=b'])
        self.assertEqual(self.connection.connection.search.call_count, 1)

    def test_get_ranged_attribute_handles_empty_echo(self):
        self._stub_ranges([
            {'member;range=0-*': [], 'member;range=0-1': ['CN=a', 'CN=b']},
            {'member;range=2-*': ['CN=c']},
        ])

        values = self.connection.get_ranged_attribute('CN=Team,DC=example,DC=com', 'member')

        self.assertEqual(values, ['CN=a', 'CN=b', 'CN=c'])

    def test_get_ranged_attribute_limit_stops_early(self):
        self._stub_ranges([
            {'member;range=0-1': ['CN=a', 'CN=b']},
            {'member;range=2-3': ['CN=c', 'CN=d']},
            {'member;range=4-*': ['CN=e']},
        ])

        values = self.connection.get_ranged_attribute(
            'CN=Team,DC=example,DC=com', 'member', limit=3
        )

        # Stops after the cap is reached and trims to exactly ``limit``.
        self.assertEqual(values, ['CN=a', 'CN=b', 'CN=c'])
        self.assertEqual(self.connection.connection.search.call_count, 2)

    def test_get_ranged_attribute_absent_object_returns_empty(self):
        def search_side_effect(**_kwargs):
            self.connection.connection.response = []
            return False

        self.connection.connection.search.side_effect = search_side_effect

        values = self.connection.get_ranged_attribute('CN=Missing,DC=example,DC=com', 'member')

        self.assertEqual(values, [])


if __name__ == '__main__':
    unittest.main()
