# ad_user_schema.py

"""
Module containing the ADUserSchema class for data validation of Active Directory user attributes
using Pydantic.
"""

# pylint: disable=duplicate-code

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator, ValidationInfo

class ADUserSchema(BaseModel):
    """
    A Pydantic model for validating and parsing Active Directory user attributes.

    This class defines the schema for an Active Directory user, including fields for user
    attributes and validators for data normalization and transformation.
    """

    # Fields definitions
    accountExpires: Optional[datetime] = None
    badPasswordTime: Optional[datetime] = None
    badPwdCount: Optional[str] = None
    cn: Optional[str] = None
    codePage: Optional[str] = None
    company: Optional[str] = None
    countryCode: Optional[str] = None
    department: Optional[str] = None
    departmentNumber: Optional[str] = None
    description: Optional[str] = None
    displayName: Optional[str] = None
    distinguishedName: Optional[str]
    division: Optional[str] = None
    employeeID: Optional[str] = None
    employeeNumber: Optional[str] = None
    extensionAttribute1: Optional[str] = None
    extensionAttribute2: Optional[str] = None
    extensionAttribute3: Optional[str] = None
    extensionAttribute4: Optional[str] = None
    extensionAttribute5: Optional[str] = None
    extensionAttribute6: Optional[str] = None
    extensionAttribute7: Optional[str] = None
    extensionAttribute8: Optional[str] = None
    extensionAttribute9: Optional[str] = None
    extensionAttribute10: Optional[str] = None
    extensionAttribute11: Optional[str] = None
    extensionAttribute12: Optional[str] = None
    extensionAttribute13: Optional[str] = None
    extensionAttribute14: Optional[str] = None
    extensionAttribute15: Optional[str] = None
    givenName: Optional[str] = None
    homeMDB: Optional[str] = None
    homePhone: Optional[str] = None
    instanceType: Optional[str] = None
    l: Optional[str] = None
    lastLogon: Optional[datetime] = None
    lastLogonTimestamp: Optional[datetime] = None
    legacyExchangeDN: Optional[str] = None
    lockoutTime: Optional[datetime] = None
    logonCount: Optional[str] = None
    mail: Optional[str] = None
    mailNickname: Optional[str] = None
    manager: Optional[str] = None
    mDBUseDefaults: Optional[str] = None
    mobile: Optional[str] = None
    name: Optional[str] = None
    objectCategory: Optional[str] = None
    objectClass: Optional[str] = None
    objectGUID: Optional[str] = None
    objectSid: Optional[str] = None
    physicalDeliveryOfficeName: Optional[str] = None
    postalCode: Optional[str] = None
    primaryGroupID: Optional[str] = None
    protocolSettings: Optional[str] = None
    proxyAddresses: Optional[str] = None
    pwdLastSet: Optional[datetime] = None
    sAMAccountName: Optional[str]
    sAMAccountType: Optional[str] = None
    sn: Optional[str] = None
    streetAddress: Optional[str] = None
    facsimileTelephoneNumber: Optional[str] = None
    postalAddress: Optional[str] = None
    telephoneNumber: Optional[str] = None
    textEncodedORAddress: Optional[str] = None
    title: Optional[str] = None
    userAccountControl: Optional[int] = None
    userPrincipalName: Optional[str]
    uSNChanged: Optional[int] = None
    uSNCreated: Optional[int] = None
    whenChanged: Optional[datetime] = None
    whenCreated: Optional[datetime] = None
    ou: Optional[str] = None
    enabled: Optional[bool] = None
    firstOrgUnitDescription: Optional[str] = None
    firstOrgUnitTelephoneNumber: Optional[str] = None
    firstOrgUnitStreet: Optional[str] = None
    firstOrgUnitPostalCode: Optional[str] = None
    changes: Optional[str] = None   # Non-database field

    @field_validator('*', mode='before')
    def general_validator(cls, value, _info: ValidationInfo):
        """
        General validator that processes all fields before standard validation.

        - Converts lists to comma-separated strings.
        - Converts integers to strings.
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
        if isinstance(value, int):
            return str(value)
        return value

    @field_validator(
        'accountExpires', 'badPasswordTime', 'lastLogon', 'lastLogonTimestamp',
        'lockoutTime', 'pwdLastSet', 'whenChanged', 'whenCreated', mode='before'
    )
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
            value = value[0] if value else None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        return value

    @field_validator('userAccountControl', mode='before')
    def parse_user_account_control(cls, value, _info: ValidationInfo):
        """
        Validator for the 'userAccountControl' field.

        - Converts the value to an integer if it's a string.

        Args:
            value: The value to validate.
            info: Validation information (unused).

        Returns:
            The processed integer value.
        """
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, str):
            value = int(value)
        return value

    @field_validator('uSNChanged', 'uSNCreated', mode='before')
    def parse_int_fields(cls, value, _info: ValidationInfo):
        """
        Validator for integer fields.

        - Converts the value to an integer if it's a string.

        Args:
            value: The value to validate.
            info: Validation information (unused).

        Returns:
            The processed integer value.
        """
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, str):
            value = int(value)
        return value

    @field_validator('employeeNumber', 'departmentNumber', 'extensionAttribute7', mode='before')
    def validate_single_value_fields(cls, value, _info: ValidationInfo):
        """
        Validator for fields that should contain a single value.

        - Extracts the first element if the value is a list.

        Args:
            value: The value to validate.
            info: Validation information (unused).

        Returns:
            The processed value.
        """
        if isinstance(value, list):
            value = value[0] if value else None
        return value

    @model_validator(mode='after')
    def set_computed_fields(self):
        """
        Model-level validator to set computed fields after validation.

        - Sets 'enabled' based on 'userAccountControl'.
        - Sets 'ou' based on 'distinguishedName'.

        Returns:
            The model instance with computed fields set.
        """
        # Set 'enabled' based on 'userAccountControl'
        if self.userAccountControl is not None:
            self.enabled = (self.userAccountControl & 2) == 0
        else:
            self.enabled = None

        # Set 'ou' based on 'distinguishedName'
        if self.distinguishedName:
            ou_parts = self.distinguishedName.split(',')[1:]
            self.ou = ','.join(ou_parts)
        else:
            self.ou = None

        return self
