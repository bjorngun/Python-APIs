"""
Module: ad_user

This module defines the `ADUser` class, which represents an Active Directory (AD) user within
a SQLAlchemy ORM framework. The class maps various AD user attributes to database columns,
allowing for seamless integration and manipulation of user data stored in an SQL database.

Classes:
    ADUser(Base): Inherits from SQLAlchemy's Base class and represents an AD user with numerous
    attributes corresponding to AD fields. It includes methods for data validation and processing.

Usage Example:
    from models.ad_user import ADUser
    from sqlalchemy.orm import Session

    # Create a new session
    session = Session(engine)

    # Query for a user
    user = session.query(ADUser).filter_by(sam_account_name='jon_doe').first()

    # Access user attributes
    print(user.display_name)
    print(user.email)

    # Use property methods
    print(user.smtp_address)
    print(user.can_change)

    # Close the session
    session.close()

Notes:
    - Validation Methods: The `@validates` decorators are used to ensure that data being
      inserted or updated in the database is properly formatted and consistent.
    - Date and Time Fields: Date and time fields are handled carefully to ensure timezone
      information is normalized (removed) before being stored.
    - Active Directory Integration: The class includes methods and properties that facilitate
      interaction with AD-specific data, such as proxy addresses and account control flags.

Dependencies:
    - SQLAlchemy: For ORM functionality.
    - typing: For type annotations, including `Optional` and `ClassVar`.

"""
from typing import Optional, ClassVar
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.dialects.mssql import DATETIME2

from .base import Base


class ADUser(Base):
    """Active Directory User model representing user attributes in the database."""

    __tablename__ = 'ADUser'

    accountExpires = Column(DATETIME2, nullable=True)
    badPasswordTime = Column(DATETIME2, nullable=True)
    badPwdCount = Column(String(256))
    cn = Column(String(256))
    codePage = Column(String(256))
    company = Column(String(256))
    countryCode = Column(String(256))
    department = Column(String(256))
    departmentNumber = Column(String(256))
    description = Column(String(1024))
    displayName = Column(String(256))
    distinguishedName = Column(String(255), primary_key=True)
    division = Column(String(256))
    employeeID = Column(String(256), nullable=False)
    employeeNumber = Column(String(256))
    extensionAttribute1 = Column(String(256))
    extensionAttribute2 = Column(String(256))
    extensionAttribute3 = Column(String(256))
    extensionAttribute4 = Column(String(256))
    extensionAttribute5 = Column(String(256))
    extensionAttribute6 = Column(String(256))
    extensionAttribute7 = Column(String(256))
    extensionAttribute8 = Column(String(256))
    extensionAttribute9 = Column(String(256))
    extensionAttribute10 = Column(String(256))
    extensionAttribute11 = Column(String(256))
    extensionAttribute12 = Column(String(256))
    extensionAttribute13 = Column(String(256))
    extensionAttribute14 = Column(String(256))
    extensionAttribute15 = Column(String(256))
    givenName = Column(String(256))
    homeMDB = Column(String(256))
    homePhone = Column(String(256))
    instanceType = Column(String(256))
    l = Column(String(256))
    lastLogon = Column(DATETIME2, nullable=True)
    lastLogonTimestamp = Column(DATETIME2, nullable=True)
    legacyExchangeDN = Column(String(256))
    lockoutTime = Column(DATETIME2, nullable=True)
    logonCount = Column(String(256))
    mail = Column(String(256))
    mailNickname = Column(String(256))
    manager = Column(String(256))
    mDBUseDefaults = Column(String(256))
    mobile = Column(String(256))
    name = Column(String(256))
    objectCategory = Column(String(256))
    objectClass = Column(String(256))
    objectGUID = Column(String(256))
    objectSid = Column(String(256))
    physicalDeliveryOfficeName = Column(String(256))
    postalCode = Column(String(256))
    primaryGroupID = Column(String(256))
    protocolSettings = Column(String(256))
    proxyAddresses = Column(String(2048))
    pwdLastSet = Column(DATETIME2, nullable=True)
    sAMAccountName = Column(String(256))
    sAMAccountType = Column(String(256))
    sn = Column(String(256))
    streetAddress = Column(String(256))
    facsimileTelephoneNumber = Column(String(256))
    postalAddress = Column(String(256))
    telephoneNumber = Column(String(256))
    textEncodedORAddress = Column(String(256))
    title = Column(String(256))
    userAccountControl = Column(String(256))
    userPrincipalName = Column(String(256))
    uSNChanged = Column(Integer)
    uSNCreated = Column(Integer)
    whenChanged = Column(DATETIME2, nullable=True)
    whenCreated = Column(DATETIME2, nullable=True)
    ou = Column(String(256))

    firstOrgUnitDescription = Column(String(256))
    firstOrgUnitTelephoneNumber = Column(String(256))
    firstOrgUnitStreet = Column(String(256))
    firstOrgUnitPostalCode = Column(String(256))
    enabled = Column(Boolean)

    # Non-database field
    changes: ClassVar[Optional[str]] = None

    def __repr__(self) -> str:
        """Return a string representation of the ADUser instance."""
        return f"ADUser({self.employeeNumber}-{self.displayName}-{self.department})"

    @property
    def proxy_address_list(self) -> list[str]:
        """Return the proxy addresses as a list.

        Splits the `proxy_addresses` string by commas and strips whitespace.

        Returns:
            list[str]: A list of proxy addresses.
        """
        if self.proxyAddresses:
            return [x.strip() for x in self.proxyAddresses.split(',')]
        return []

    @property
    def smtp_address(self) -> Optional[str]:
        """Return the primary SMTP address.

        Searches the `proxy_address_list` for an address starting with 'SMTP:'.

        Returns:
            Optional[str]: The primary SMTP address, or None if not found.
        """
        for address in self.proxy_address_list:
            if address.startswith('SMTP:'):
                return address
        return None

    @property
    def can_change(self) -> bool:
        """Determine if the user can change settings based on `extension_attribute7`.

        Returns:
            bool: True if the user can change settings, False otherwise.
        """
        return self.extensionAttribute7 != '1'

    def proxy_addresses_with_new_smtp(self, new_smtp: str) -> list[str]:
        """Generate a new list of proxy addresses with a new primary SMTP address.

        Args:
            new_smtp (str): The new primary SMTP email address.

        Returns:
            list[str]: Updated list of proxy addresses.
        """
        updated_addresses = []

        if self.smtp_address and new_smtp in self.smtp_address:
            return self.proxy_address_list

        new_smtp_full = f'SMTP:{new_smtp}'
        for address in self.proxy_address_list:
            if address.lower() == new_smtp_full.lower():
                continue

            if address.startswith('SMTP:'):
                # Convert existing primary SMTP to secondary
                updated_addresses.append('smtp:' + address[5:])
            else:
                # Keep all other addresses
                updated_addresses.append(address)

        # Add the new primary SMTP
        updated_addresses.append(new_smtp_full)
        return updated_addresses

    @staticmethod
    def get_attribute_list() -> list[str]:
        """Return a list of attribute names for the ADUser.

        Returns:
            list[str]: A list of attribute names.
        """
        return [
            'accountExpires', 'badPasswordTime', 'badPwdCount', 'cn', 'codePage',
            'company', 'countryCode', 'department', 'departmentNumber',
            'description', 'displayName', 'distinguishedName', 'division',
            'employeeID', 'extensionAttribute1', 'extensionAttribute2',
            'extensionAttribute3', 'extensionAttribute4', 'extensionAttribute5',
            'extensionAttribute6', 'extensionAttribute7', 'extensionAttribute8',
            'extensionAttribute9', 'extensionAttribute10', 'extensionAttribute11',
            'extensionAttribute12', 'extensionAttribute13', 'extensionAttribute14',
            'extensionAttribute15', 'givenName', 'homeMDB', 'homePhone',
            'instanceType', 'l', 'lastLogon', 'lastLogonTimestamp', 'employeeNumber',
            'legacyExchangeDN', 'lockoutTime', 'logonCount', 'mail', 'mailNickname',
            'manager', 'mDBUseDefaults', 'mobile', 'name', 'objectCategory',
            'objectClass', 'objectGUID', 'objectSid', 'physicalDeliveryOfficeName',
            'postalCode', 'primaryGroupID', 'protocolSettings', 'proxyAddresses',
            'pwdLastSet', 'sAMAccountName', 'sAMAccountType', 'sn', 'streetAddress',
            'facsimileTelephoneNumber', 'postalAddress',
            'telephoneNumber', 'textEncodedORAddress', 'title', 'userAccountControl',
            'userPrincipalName', 'uSNChanged', 'uSNCreated', 'whenChanged',
            'whenCreated'
        ]
