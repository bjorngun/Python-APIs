""" Module: ad_ou

This module defines the ADOrganizationalUnit class, which represents an Active Directory (AD)
Organizational Unit (OU) within a SQLAlchemy ORM framework. The class maps various AD OU attributes
to database columns with names exactly matching those in Active Directory, allowing for seamless
integration and manipulation of OU data stored in an SQL database while maintaining consistency
with AD attribute naming conventions.

Classes: ADOrganizationalUnit(Base): Inherits from SQLAlchemy's Base class and represents an AD OU
with attributes corresponding to AD fields. It includes methods for parsing distinguished names,
navigating the OU hierarchy, and accessing related child and parent OUs.

Usage Example: ```python from models.ad_ou import ADOrganizationalUnit from sqlalchemy.orm import
Session

# Create a new session
session = Session(engine)

# Query for an OU
ou = session.query(ADOrganizationalUnit).filter_by(name='Engineering').first()

# Access OU attributes
print(ou.name)
print(ou.description)

# Use property methods
print(ou.parentOUName)
print(ou.childOUNames)
print(ou.getFullPath())

# Close the session
session.close()
```
Notes: - Field Naming: The class attributes are named exactly as they are in Active Directory to
maintain consistency and avoid confusion when mapping AD data. - Validation Methods: The @validates
decorators can be used to ensure that data being inserted or updated in the database is properly
formatted and consistent. - Active Directory Integration: The class includes methods and properties
that facilitate interaction with AD-specific data, such as parsing distinguished names to determine
hierarchy.

Dependencies: - SQLAlchemy: For ORM functionality. - typing: For type annotations, including
Optional and ClassVar.

"""


from typing import Any, Optional, ClassVar
from ldap3.core.exceptions import LDAPInvalidDnError
from ldap3.utils.dn import parse_dn
from sqlalchemy import Column, String
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import reconstructor

from .base import Base

class NotSetException(Exception):
    """
    Exception raised when a required variable or attribute is accessed but has not been set.
    """
    def __init__(self, variable_name=None, message="The required variable has not been set."):
        if variable_name:
            message = f"The variable '{variable_name}' has not been set."
        super().__init__(message)


class ADOrganizationalUnit(Base):
    """Active Directory Organizational Unit model representing OU attributes in the database."""

    __tablename__ = 'ADOrganizationalUnit'
    __allow_unmapped__ = True

    distinguishedName = Column(String(255), primary_key=True)
    name = Column(String(256))
    ou = Column(String(256))
    description = Column(String(1024))
    whenCreated = Column(DATETIME2, nullable=True)
    whenChanged = Column(DATETIME2, nullable=True)
    objectClass = Column(String(256))
    objectGUID = Column(String(256))
    objectSid = Column(String(256))
    managedBy = Column(String(256))
    l = Column(String(256))  # Location
    street = Column(String(256))
    streetAddress = Column(String(256))
    postalCode = Column(String(256))
    telephoneNumber = Column(String(256))

    # Non-database field
    changes: ClassVar[Optional[str]] = None
    children: list['ADOrganizationalUnit']
    parent: Optional['ADOrganizationalUnit']
    ldap_attributes: dict[str, Any]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._initialize_hierarchy()

    @reconstructor
    def _initialize_hierarchy(self) -> None:
        """Initialize non-persistent hierarchy links for each model instance."""
        self.children = []
        self.parent = None
        self.ldap_attributes = {}

    def __repr__(self) -> str:
        """Return a string representation of the ADOrganizationalUnit instance."""
        return f"ADOrganizationalUnit({self.name})"

    @property
    def parent_ou_distinguished_name(self) -> Optional[str]:
        """Return the distinguishedName of the parent OU, if any.

        Parses the `distinguishedName` to extract the parent distinguishedName.

        Returns:
            Optional[str]: The name of the parent OU, or None if it doesn't exist.
        """
        components = self.parse_distinguished_name()
        if len(components) < 2:
            return None
        return ','.join(components[1:])

    @property
    def child_ou_names(self) -> list[str]:
        """Return a list of names of all child OUs.

        Returns:
            list[str]: A list of child OU names.
        """
        return [str(child.name) for child in self.children if child.name is not None]

    def parse_distinguished_name(self) -> list[str]:
        """Parse the distinguished name into LDAP-aware RDN components.

        Returns:
            list[str]: RDN strings with LDAP escaping preserved.

        Raises:
            ValueError: If the distinguished name is absent or malformed.
        """
        distinguished_name = self.distinguishedName
        if not isinstance(distinguished_name, str) or not distinguished_name.strip():
            raise ValueError("Invalid distinguished name")
        try:
            parsed_components = parse_dn(distinguished_name, escape=True, strip=True)
        except LDAPInvalidDnError as exc:
            raise ValueError("Invalid distinguished name") from exc

        relative_names: list[str] = []
        current_parts: list[str] = []
        for attribute, value, separator in parsed_components:
            current_parts.append(f"{attribute}={value}")
            if separator != '+':
                relative_names.append('+'.join(current_parts))
                current_parts = []
        if current_parts:
            relative_names.append('+'.join(current_parts))
        return relative_names

    def get_hierarchy(self) -> list[str]:
        """Get the hierarchy of OUs from the root to this OU.

        Returns:
            list[str]: A list of OU names from the root to this OU.
        """
        hierarchy: list[str] = []
        parts = self.parse_distinguished_name()
        for part in parts:
            for attribute, value, _separator in parse_dn(part, escape=True, strip=True):
                if attribute.casefold() == 'ou':
                    hierarchy.insert(0, value)
        return hierarchy

    def get_full_path(self) -> str:
        """Get the full path of the OU hierarchy.

        Returns:
            str: A string representing the full path of the OU.
        """
        return '/'.join(self.get_hierarchy())

    @staticmethod
    def get_attribute_list() -> list[str]:
        """Return a list of attribute names for the AD OU.

        Returns:
            list[str]: A list of attribute names.
        """
        return [
            'distinguishedName', 'name', 'ou', 'description', 'whenCreated',
            'whenChanged', 'objectClass', 'objectGUID', 'objectSid',
            'managedBy', 'l', 'street', 'streetAddress', 'postalCode', 'telephoneNumber'
        ]
