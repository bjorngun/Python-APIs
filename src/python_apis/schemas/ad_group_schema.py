# ad_group_schema.py

"""
Module containing the ADGroupSchema class for data validation of Active Directory
Group attributes using Pydantic.
"""

# pylint: disable=duplicate-code

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator, ValidationInfo


class ADGroupSchema(BaseModel):
    """
    A Pydantic model for validating and parsing Active Directory Group attributes.

    This class defines the schema for an Active Directory Group, including fields for Group
    attributes and validators for data normalization and transformation.
    """

    # Field definitions
    cn: Optional[str] = None
    description: Optional[str] = None
    distinguishedName: str
    ou: Optional[str] = None
    groupType: Optional[int] = None
    instanceType: Optional[int]
    sAMAccountType: Optional[int]
    managedBy: Optional[str] = None
    name: str
    objectCategory: Optional[str] = None
    objectClass: Optional[str] = None
    objectGUID: Optional[str] = None
    objectSid: Optional[str] = None
    sAMAccountName: Optional[str] = None
    uSNChanged: Optional[int] = None
    uSNCreated: Optional[int] = None
    whenChanged: Optional[datetime] = None
    whenCreated: Optional[datetime] = None
    extensionName: Optional[str] = None

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

    @property
    def member_count(self) -> int:
        """
        Property to get the count of members in the group.

        Returns:
            int: The number of members in the group.
        """
        return len(self.member) if self.member else 0
