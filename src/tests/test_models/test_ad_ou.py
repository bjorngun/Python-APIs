"""Tests for LDAP-aware organizational-unit distinguished names."""

import unittest

from python_apis.models import ADOrganizationalUnit


class TestADOrganizationalUnitDistinguishedName(unittest.TestCase):
    """Validate safe DN parsing and hierarchy derivation."""

    @staticmethod
    def _ou(distinguished_name: str) -> ADOrganizationalUnit:
        return ADOrganizationalUnit(
            distinguishedName=distinguished_name,
            name='Test OU',
        )

    def test_parse_distinguished_name_preserves_escaped_comma(self):
        ou = self._ou(
            r'OU=Research\, Development,OU=Parent,DC=example,DC=com'
        )

        self.assertEqual(
            ou.parse_distinguished_name(),
            [
                r'OU=Research\, Development',
                'OU=Parent',
                'DC=example',
                'DC=com',
            ],
        )

    def test_parse_distinguished_name_preserves_equals_and_backslash(self):
        ou = self._ou(r'OU=Name\=Value,OU=Back\\Slash,DC=example,DC=com')

        self.assertEqual(
            ou.parse_distinguished_name(),
            [r'OU=Name\=Value', r'OU=Back\\Slash', 'DC=example', 'DC=com'],
        )

    def test_parent_dn_drops_complete_first_multivalued_rdn(self):
        ou = self._ou(
            r'OU=Research\, Development+CN=Alias,OU=Parent,DC=example,DC=com'
        )

        self.assertEqual(
            ou.parent_ou_distinguished_name,
            'OU=Parent,DC=example,DC=com',
        )

    def test_hierarchy_recognizes_mixed_case_ou_attributes(self):
        ou = self._ou('ou=Child,Ou=Parent,DC=example,DC=com')

        self.assertEqual(ou.get_hierarchy(), ['Parent', 'Child'])
        self.assertEqual(ou.get_full_path(), 'Parent/Child')

    def test_single_rdn_has_no_parent(self):
        ou = self._ou('DC=com')

        self.assertIsNone(ou.parent_ou_distinguished_name)

    def test_malformed_dn_raises_safe_value_error(self):
        ou = self._ou('not-a-distinguished-name')

        with self.assertRaisesRegex(ValueError, '^Invalid distinguished name$') as context:
            ou.parse_distinguished_name()

        self.assertNotIn('not-a-distinguished-name', str(context.exception))


if __name__ == '__main__':
    unittest.main()
