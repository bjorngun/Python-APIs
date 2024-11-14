"""
Module: schemas

This module initializes and exposes the Pydantic schemas for the Python APIs models, specifically
for Active Directory (AD) User and Organizational Unit (OU) data validation.

The schemas are designed to:

- Provide a structured way to validate and parse data related to AD users and OUs.
- Ensure data integrity when fetching data from sources other than the database, such as external
APIs or LDAP queries.
- Facilitate the creation of new services by providing ready-to-use data models.

Available Schemas:
    - ADUserSchema: Validates and parses Active Directory user attributes.
    - ADOrganizationalUnitSchema: Validates and parses Active Directory Organizational Unit
    attributes.

Usage:
    ```python
    from python_apis.schemas import ADUserSchema, ADOrganizationalUnitSchema

    # Example usage for ADUserSchema
    user_data = {
        'distinguishedName': 'CN=John Doe,OU=Users,DC=example,DC=com',
        'sAMAccountName': 'jdoe',
        'userPrincipalName': 'jdoe@example.com',
        # ... other user attributes
    }
    user = ADUserSchema(**user_data)
    print(user.displayName)

    # Example usage for ADOrganizationalUnitSchema
    ou_data = {
        'distinguishedName': 'OU=Engineering,DC=example,DC=com',
        'name': 'Engineering',
        # ... other OU attributes
    }
    ou = ADOrganizationalUnitSchema(**ou_data)
    print(ou.full_path)
    ```

Notes:
    - It's recommended to use these schemas for data validation when working with AD data fetched
    from external sources.
    - The schemas ensure that the data conforms to the expected structure and types defined by the
    models.

"""

from python_apis.schemas.ad_user_schema import ADUserSchema
from python_apis.schemas.ad_group_schema import ADGroupSchema
from python_apis.schemas.ad_ou_schema import ADOrganizationalUnitSchema

__all__ = [
    "ADUserSchema",
    "ADGroupSchema",
    "ADOrganizationalUnitSchema",
]
