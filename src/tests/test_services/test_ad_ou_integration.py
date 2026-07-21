"""Public integration tests for generic OU tree and inheritance APIs."""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from python_apis.apis import (
    ADBindError,
    ADConnectionError,
    ADMissingServersError,
)
from python_apis.services import (
    ADOrganizationalUnitService,
    ADOrganizationalUnitTreeError,
    OUAttributeRule,
    OUInheritanceCycleError,
)


class TestADResiliencePublicExports(unittest.TestCase):
    """Validate stable public import paths and exception relationships."""

    def test_connection_errors_are_public(self):
        self.assertTrue(issubclass(ADBindError, ADConnectionError))
        self.assertTrue(issubclass(ADMissingServersError, Exception))

    def test_ou_types_are_public(self):
        self.assertTrue(issubclass(ADOrganizationalUnitTreeError, ValueError))
        self.assertTrue(issubclass(OUInheritanceCycleError, ValueError))
        self.assertEqual(OUAttributeRule(source='description').source, 'description')


class TestGenericOUIntegration(unittest.TestCase):
    """Exercise one-query tree loading and ordered mixed-object resolution."""

    def test_ad_only_factory_does_not_initialize_sql_or_environment(self):
        ad_connection = MagicMock()

        service = ADOrganizationalUnitService.for_active_directory(ad_connection)

        self.assertIs(service.ad_connection, ad_connection)
        self.assertIsNone(service.sql_connection)

    def test_bulk_resolution_uses_one_tree_query_for_mixed_objects(self):
        root_dn = 'OU=Root,DC=example,DC=com'
        child_dn = f'OU=Child,{root_dn}'
        ad_connection = MagicMock()
        ad_connection.search.return_value = [
            {
                'distinguishedName': root_dn,
                'description': '100',
                'streetAddress': 'Main Street 1',
            },
            {
                'distinguishedName': child_dn,
                'description': '200',
            },
        ]
        service = ADOrganizationalUnitService(
            ad_connection=ad_connection,
            sql_connection=MagicMock(),
        )
        objects = [
            {'ou_dn': child_dn},
            SimpleNamespace(ou_dn=root_dn),
        ]
        rules = {
            'department_code': OUAttributeRule(source='description'),
            'office_address': OUAttributeRule(
                source='street',
                aliases=('streetAddress',),
            ),
        }

        def get_ou_dn(item: object) -> str | None:
            if isinstance(item, dict):
                return item.get('ou_dn')
            return getattr(item, 'ou_dn', None)

        resolved = service.resolve_inherited_attributes_for_objects(
            objects,
            rules,
            get_ou_dn=get_ou_dn,
        )

        ad_connection.search.assert_called_once()
        self.assertEqual(
            resolved,
            [
                {'department_code': '200', 'office_address': 'Main Street 1'},
                {'department_code': '100', 'office_address': 'Main Street 1'},
            ],
        )
        self.assertEqual(objects[0], {'ou_dn': child_dn})
        self.assertEqual(objects[1].ou_dn, root_dn)


if __name__ == '__main__':
    unittest.main()
