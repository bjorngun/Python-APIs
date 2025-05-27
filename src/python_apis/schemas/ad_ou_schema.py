# ad_ou_schema.py

"""
Module containing the ADOrganizationalUnitSchema class for data validation of Active Directory
Organizational Unit (OU) attributes using Pydantic.
"""

# pylint: disable=duplicate-code

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator, ValidationInfo


class ADOrganizationalUnitSchema(BaseModel):
    """
    A Pydantic model for validating and parsing Active Directory Organizational Unit (OU)
    attributes.

    This class defines the schema for an Active Directory OU, including fields for OU attributes
    and validators for data normalization and transformation.
    """

    # Fields definitions
    distinguishedName: str
    name: Optional[str] = None
    ou: Optional[str] = None
    description: Optional[str] = None
    whenCreated: Optional[datetime] = None
    whenChanged: Optional[datetime] = None
    objectClass: Optional[str] = None
    objectGUID: Optional[str] = None
    objectSid: Optional[str] = None
    managedBy: Optional[str] = None
    l: Optional[str] = None  # Location
    streetAddress: Optional[str] = None
    postalCode: Optional[str] = None
    telephoneNumber: Optional[str] = None
    changes: Optional[str] = None  # Non-database field

    @field_validator('*', mode='before')
    def general_validator(cls, value, _info: ValidationInfo):
        """
        General validator that processes all fields before standard validation.

        - Converts lists to comma-separated strings.
        - Returns None for empty lists.

        Args:
            value: The value to validate.
            info: Validation information (unused).

        Returns:
            The processed value.
        """
        if isinstance(value, list):
            if not value:
                return None
            return ','.join(map(str, value))
        return value

    @field_validator('whenCreated', 'whenChanged', mode='before')
    def parse_datetime(cls, value, _info: ValidationInfo):
        """
        Validator for datetime fields.

        - Extracts the first element if the value is a list.
        - Removes timezone information from datetime objects.

        Args:
            value: The value to validate.
            info: Validation information (unused).

        Returns:
            The processed datetime value.
        """
        if isinstance(value, list):
            value = ','.join(map(str, value))
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        return value

    @field_validator('description', mode='before')
    def parse_description(cls, value, _info: ValidationInfo):
        """
        Validator for the 'description' field.

        - Converts the value to a str if it is a list.
        - Takes out the character "-" if it has one. i.e. 21-420 -> 21420

        Args:
            value: The value to validate.
            info: Validation information (unused).

        Returns:
            The processed str value.
        """
        if isinstance(value, list):
            if not value:
                return None
            value = ','.join(map(str, value))
        return value.replace('-', '')

    @property
    def ou_hierarchy(self) -> list[str]:
        """
        Property to get the hierarchy of OUs from the root to this OU.

        Returns:
            list[str]: A list of OU names from the root to this OU.
        """
        hierarchy = []
        if self.distinguishedName:
            parts = self.distinguishedName.split(',')
            for part in parts:
                if part.startswith('OU='):
                    hierarchy.insert(0, part[3:])
        return hierarchy

    @property
    def full_path(self) -> str:
        """
        Property to get the full path of the OU hierarchy.

        Returns:
            str: A string representing the full path of the OU.
        """
        return '/'.join(self.ou_hierarchy)
