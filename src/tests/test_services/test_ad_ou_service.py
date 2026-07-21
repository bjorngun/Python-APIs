"""Tests for Active Directory organizational-unit hierarchy behavior."""

import unittest

from python_apis.models import ADOrganizationalUnit
from python_apis.services.ad_ou_service import ADOrganizationalUnitService


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


if __name__ == '__main__':
    unittest.main()
