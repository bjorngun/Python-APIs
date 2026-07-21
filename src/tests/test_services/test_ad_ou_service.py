"""Tests for Active Directory organizational-unit hierarchy behavior."""

import unittest
from unittest.mock import MagicMock

from ldap3 import SUBTREE

from python_apis.models import ADOrganizationalUnit
from python_apis.services.ad_ou_service import (
    ADOrganizationalUnitService,
    ADOrganizationalUnitTreeError,
)


class TestADOrganizationalUnitRelationships(unittest.TestCase):
    """Validate parent/child linking through parsed distinguished names."""

    def test_set_ou_children_and_parent_uses_ldap_aware_parent_dn(self):
        parent = ADOrganizationalUnit(
            distinguishedName=r'OU=Research\, Development,DC=example,DC=com',
            name='Research, Development',
        )
        child = ADOrganizationalUnit(
            distinguishedName=(
                r'OU=Platform,OU=Research\, Development,DC=example,DC=com'
            ),
            name='Platform',
        )
        parent.children = []
        child.children = []
        service = ADOrganizationalUnitService.__new__(ADOrganizationalUnitService)

        service.set_ou_children_and_parent({
            parent.distinguishedName: parent,
            child.distinguishedName: child,
        })

        self.assertIs(child.parent, parent)
        self.assertEqual(parent.children, [child])

    def test_missing_parent_leaves_ou_unlinked(self):
        orphan = ADOrganizationalUnit(
            distinguishedName='OU=Orphan,OU=Missing,DC=example,DC=com',
            name='Orphan',
        )
        orphan.children = []
        orphan.parent = None
        service = ADOrganizationalUnitService.__new__(ADOrganizationalUnitService)

        service.set_ou_children_and_parent({orphan.distinguishedName: orphan})

        self.assertIsNone(orphan.parent)
        self.assertEqual(orphan.children, [])

    def test_parent_link_uses_canonical_dn_equivalence(self):
        parent = ADOrganizationalUnit(
            distinguishedName=r'OU=Research\, Development,DC=Example,DC=COM',
            name='Research, Development',
        )
        child = ADOrganizationalUnit(
            distinguishedName=(
                r'ou=platform,ou=research\2C development,dc=example,dc=com'
            ),
            name='Platform',
        )
        service = ADOrganizationalUnitService.__new__(ADOrganizationalUnitService)

        service.set_ou_children_and_parent({
            parent.distinguishedName: parent,
            child.distinguishedName: child,
        })

        self.assertIs(child.parent, parent)
        self.assertEqual(parent.children, [child])


class TestADOrganizationalUnitTree(unittest.TestCase):
    """Validate single-query OU tree construction and defensive normalization."""

    def setUp(self):
        self.ad_connection = MagicMock()
        self.service = ADOrganizationalUnitService.__new__(ADOrganizationalUnitService)
        self.service.ad_connection = self.ad_connection

    def test_get_ou_tree_builds_relationships_with_one_subtree_query(self):
        parent_dn = r'OU=Research\, Development,DC=example,DC=com'
        child_dn = rf'OU=Platform,{parent_dn}'
        self.ad_connection.search.return_value = [
            {
                'distinguishedName': [parent_dn],
                'description': ['12-34'],
                'street': [],
                'telephoneNumber': ['5551000', '5551001'],
                'extensionAttribute1': ['Custom value'],
            },
            {
                'distinguishedName': child_dn,
                'description': None,
                'streetAddress': ['Main Street 1'],
            },
        ]

        tree = self.service.get_ou_tree(
            attributes=[
                'description',
                'distinguishedName',
                'street',
                'streetAddress',
                'description',
                'telephoneNumber',
                'extensionAttribute1',
            ],
            search_base='OU=Departments,DC=example,DC=com',
        )

        self.ad_connection.search.assert_called_once_with(
            '(objectClass=organizationalUnit)',
            [
                'description',
                'distinguishedName',
                'street',
                'streetAddress',
                'telephoneNumber',
                'extensionAttribute1',
            ],
            search_base='OU=Departments,DC=example,DC=com',
            search_scope=SUBTREE,
        )
        self.assertEqual(set(tree), {parent_dn, child_dn})
        self.assertIs(tree[child_dn].parent, tree[parent_dn])
        self.assertEqual(tree[parent_dn].children, [tree[child_dn]])
        self.assertEqual(tree[parent_dn].description, '12-34')
        self.assertIsNone(tree[parent_dn].ldap_attributes['street'])
        self.assertEqual(tree[parent_dn].telephoneNumber, '5551000,5551001')
        self.assertEqual(
            tree[parent_dn].ldap_attributes['extensionAttribute1'],
            'Custom value',
        )
        self.assertEqual(tree[child_dn].streetAddress, 'Main Street 1')

    def test_get_ou_tree_default_attributes_include_generic_street_forms(self):
        self.ad_connection.search.return_value = []

        self.service.get_ou_tree()

        attributes = self.ad_connection.search.call_args.args[1]
        self.assertEqual(attributes.count('distinguishedName'), 1)
        self.assertIn('street', attributes)
        self.assertIn('streetAddress', attributes)

    def test_get_ou_tree_keeps_missing_parent_as_orphan(self):
        orphan_dn = 'OU=Child,OU=Missing,DC=example,DC=com'
        self.ad_connection.search.return_value = [
            {'distinguishedName': orphan_dn},
        ]

        tree = self.service.get_ou_tree(attributes=[])

        self.assertIsNone(tree[orphan_dn].parent)
        self.assertEqual(tree[orphan_dn].children, [])

    def test_get_ou_tree_rejects_missing_dn_without_silent_drop(self):
        self.ad_connection.search.return_value = [{'description': 'No DN'}]

        with self.assertRaisesRegex(
            ADOrganizationalUnitTreeError,
            'entry 0: missing distinguishedName',
        ):
            self.service.get_ou_tree()

    def test_get_ou_tree_rejects_malformed_dn_with_safe_error(self):
        self.ad_connection.search.return_value = [
            {'distinguishedName': 'not-a-distinguished-name'},
        ]

        with self.assertRaisesRegex(
            ADOrganizationalUnitTreeError,
            'entry 0: invalid organizational unit',
        ) as context:
            self.service.get_ou_tree()

        self.assertNotIn('not-a-distinguished-name', str(context.exception))

    def test_get_ou_tree_rejects_duplicate_dn(self):
        distinguished_name = 'OU=Duplicate,DC=example,DC=com'
        self.ad_connection.search.return_value = [
            {'distinguishedName': distinguished_name},
            {'distinguishedName': distinguished_name},
        ]

        with self.assertRaisesRegex(
            ADOrganizationalUnitTreeError,
            'entry 1: duplicate distinguishedName',
        ):
            self.service.get_ou_tree()

    def test_get_ou_tree_rejects_ldap_equivalent_duplicate_dn(self):
        self.ad_connection.search.return_value = [
            {'distinguishedName': r'OU=Research\, Development,DC=Example,DC=COM'},
            {'distinguishedName': r'ou=research\2C development,dc=example,dc=com'},
        ]

        with self.assertRaisesRegex(
            ADOrganizationalUnitTreeError,
            'entry 1: duplicate distinguishedName',
        ):
            self.service.get_ou_tree()

    def test_street_is_ldap_only_and_not_an_orm_column(self):
        self.assertNotIn('street', ADOrganizationalUnit.__table__.columns)

    def test_get_ou_tree_validates_requested_attributes_before_search(self):
        with self.assertRaisesRegex(ValueError, 'OU attributes'):
            self.service.get_ou_tree(attributes=['description', ''])

        self.ad_connection.search.assert_not_called()


if __name__ == '__main__':
    unittest.main()
