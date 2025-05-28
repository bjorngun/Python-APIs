import unittest
from unittest.mock import patch

from python_apis.services.ad_ou_service import ADOrganizationalUnitService


class TestADOrganizationalUnitServiceAttributes(unittest.TestCase):
    """Tests for the attributes helper of ADOrganizationalUnitService."""

    @patch(
        'python_apis.services.ad_ou_service.ADOrganizationalUnit.get_attribute_list'
    )
    def test_attributes_returns_model_list(self, mock_get_attr_list):
        mock_get_attr_list.return_value = ['dn', 'name']

        attrs = ADOrganizationalUnitService.attributes()

        mock_get_attr_list.assert_called_once_with()
        self.assertEqual(attrs, ['dn', 'name'])


if __name__ == '__main__':
    unittest.main()
