"""Tests for consumer-neutral OU inheritance rules."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from python_apis.models import ADOrganizationalUnit
from python_apis.services.ad_ou_service import ADOrganizationalUnitService
from python_apis.services.ou_inheritance import (
    OUAttributeRule,
    OUInheritanceCycleError,
)


class TestOUAttributeRuleResolution(unittest.TestCase):
    """Validate nearest-first normalization, acceptance, aliases, and defaults."""

    def setUp(self):
        self.root = ADOrganizationalUnit(
            distinguishedName='OU=Root,DC=example,DC=com',
            description='12-34',
            telephoneNumber='5551000',
            streetAddress='Main Street 1',
        )
        self.child = ADOrganizationalUnit(
            distinguishedName='OU=Child,OU=Root,DC=example,DC=com',
            description='not numeric',
        )
        self.child.parent = self.root
        self.root.children.append(self.child)
        self.tree = {
            self.root.distinguishedName: self.root,
            self.child.distinguishedName: self.child,
        }
        self.service = ADOrganizationalUnitService.__new__(ADOrganizationalUnitService)

    def test_nearest_acceptable_value_wins_after_normalization(self):
        rules = {
            'department_code': OUAttributeRule(
                source='description',
                normalize=lambda value: str(value).replace('-', ''),
                accept=lambda value: str(value).isdigit(),
            ),
        }

        resolved = self.service.resolve_inherited_attributes(
            self.child.distinguishedName,
            rules,
            ou_tree=self.tree,
        )

        self.assertEqual(resolved, {'department_code': '1234'})
        self.assertEqual(self.root.description, '12-34')
        self.assertEqual(self.child.description, 'not numeric')

    def test_alias_is_used_when_source_is_empty(self):
        rules = {
            'office_address': OUAttributeRule(
                source='street',
                aliases=('streetAddress',),
            ),
        }

        resolved = self.service.resolve_inherited_attributes(
            self.child.distinguishedName,
            rules,
            ou_tree=self.tree,
        )

        self.assertEqual(resolved, {'office_address': 'Main Street 1'})

    def test_arbitrary_ldap_attribute_is_resolved_case_insensitively(self):
        self.root.ldap_attributes['extensionAttribute1'] = 'Custom value'
        rules = {
            'custom': OUAttributeRule(source='extensionattribute1'),
        }

        resolved = self.service.resolve_inherited_attributes(
            self.child.distinguishedName,
            rules,
            ou_tree=self.tree,
        )

        self.assertEqual(resolved, {'custom': 'Custom value'})

    def test_defaults_are_returned_for_missing_start_and_values(self):
        rules = {
            'phone': OUAttributeRule(source='mobile', default='not configured'),
        }

        resolved = self.service.resolve_inherited_attributes(
            'OU=Missing,DC=example,DC=com',
            rules,
            ou_tree=self.tree,
        )

        self.assertEqual(resolved, {'phone': 'not configured'})

    def test_equivalent_caller_dn_resolves_existing_ou(self):
        resolved = self.service.resolve_inherited_attributes(
            'ou=child,ou=root,dc=EXAMPLE,dc=COM',
            {'phone': OUAttributeRule(source='telephoneNumber')},
            ou_tree=self.tree,
        )

        self.assertEqual(resolved, {'phone': '5551000'})

    def test_cycle_is_detected_before_values_are_returned(self):
        self.root.parent = self.child
        rules = {
            'phone': OUAttributeRule(source='telephoneNumber'),
        }

        with self.assertRaisesRegex(
            OUInheritanceCycleError,
            '^Cycle detected in OU hierarchy$',
        ):
            self.service.resolve_inherited_attributes(
                self.child.distinguishedName,
                rules,
                ou_tree=self.tree,
            )

    def test_invalid_rules_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, 'source'):
            OUAttributeRule(source='')
        with self.assertRaisesRegex(ValueError, 'unique'):
            OUAttributeRule(source='street', aliases=('STREET',))
        with self.assertRaisesRegex(ValueError, 'targets'):
            self.service.resolve_inherited_attributes(
                self.child.distinguishedName,
                {'': OUAttributeRule(source='street')},
                ou_tree=self.tree,
            )


class TestBulkOUAttributeResolution(unittest.TestCase):
    """Validate ordered bulk resolution without per-object LDAP queries."""

    def setUp(self):
        self.root = ADOrganizationalUnit(
            distinguishedName='OU=Root,DC=example,DC=com',
            description='100',
            streetAddress='Main Street 1',
        )
        self.child = ADOrganizationalUnit(
            distinguishedName='OU=Child,OU=Root,DC=example,DC=com',
            description='200',
        )
        self.child.parent = self.root
        self.tree = {
            self.root.distinguishedName: self.root,
            self.child.distinguishedName: self.child,
        }
        self.service = ADOrganizationalUnitService.__new__(ADOrganizationalUnitService)
        self.service.get_ou_tree = MagicMock(return_value=self.tree)
        self.rules = {
            'code': OUAttributeRule(source='description'),
            'address': OUAttributeRule(
                source='street',
                aliases=('streetAddress',),
            ),
        }

    def test_mapping_inputs_load_one_tree_and_preserve_order(self):
        objects = [
            {'ou_dn': self.child.distinguishedName},
            {'ou_dn': self.root.distinguishedName},
            {'ou_dn': self.child.distinguishedName},
        ]

        resolved = self.service.resolve_inherited_attributes_for_objects(
            objects,
            self.rules,
            distinguished_name_attribute='ou_dn',
            search_base='OU=Departments,DC=example,DC=com',
        )

        self.service.get_ou_tree.assert_called_once_with(
            attributes=['description', 'street', 'streetAddress'],
            search_base='OU=Departments,DC=example,DC=com',
        )
        self.assertEqual(
            resolved,
            [
                {'code': '200', 'address': 'Main Street 1'},
                {'code': '100', 'address': 'Main Street 1'},
                {'code': '200', 'address': 'Main Street 1'},
            ],
        )
        self.assertIsNot(resolved[0], resolved[2])
        self.assertEqual(objects[0], {'ou_dn': self.child.distinguishedName})

    def test_plain_objects_use_dn_extractor_with_preloaded_tree(self):
        objects = [
            SimpleNamespace(location=self.root.distinguishedName),
            SimpleNamespace(location=self.child.distinguishedName),
        ]

        resolved = self.service.resolve_inherited_attributes_for_objects(
            objects,
            self.rules,
            get_ou_dn=lambda item: item.location,
            ou_tree=self.tree,
        )

        self.service.get_ou_tree.assert_not_called()
        self.assertEqual([item['code'] for item in resolved], ['100', '200'])
        self.assertEqual(objects[0].location, self.root.distinguishedName)

    def test_empty_input_does_not_load_tree(self):
        resolved = self.service.resolve_inherited_attributes_for_objects([], self.rules)

        self.assertEqual(resolved, [])
        self.service.get_ou_tree.assert_not_called()

    def test_missing_object_dn_fails_with_safe_index(self):
        objects = [{'ou_dn': self.root.distinguishedName}, {'name': 'No OU'}]

        with self.assertRaisesRegex(
            ValueError,
            '^Object at index 1 has no OU distinguished name$',
        ):
            self.service.resolve_inherited_attributes_for_objects(
                objects,
                self.rules,
                distinguished_name_attribute='ou_dn',
                ou_tree=self.tree,
            )

    def test_invalid_extractor_fails_before_tree_load(self):
        with self.assertRaisesRegex(ValueError, 'get_ou_dn'):
            self.service.resolve_inherited_attributes_for_objects(
                [{'ou': self.root.distinguishedName}],
                self.rules,
                get_ou_dn='not callable',
            )

        self.service.get_ou_tree.assert_not_called()


if __name__ == '__main__':
    unittest.main()
