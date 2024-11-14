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


from typing import Optional, ClassVar
from sqlalchemy import Column, String
from sqlalchemy.dialects.mssql import DATETIME2

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
    streetAddress = Column(String(256))
    postalCode = Column(String(256))
    telephoneNumber = Column(String(256))

    # Non-database field
    changes: ClassVar[Optional[str]] = None
    children: ClassVar[Optional[list['ADOrganizationalUnit']]] = None
    parent: ClassVar[Optional['ADOrganizationalUnit']] = None

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
        if len(self.parse_distinguished_name()) < 1:
            return None
        return ','.join(self.parse_distinguished_name()[:-1])

    @property
    def child_ou_names(self) -> list[str]:
        """Return a list of names of all child OUs.

        Returns:
            list[str]: A list of child OU names.
        """
        if self.children is None:
            raise NotSetException(variable_name="children")
        self.children: list[ADOrganizationalUnit]
        return [child.name for child in self.children]

    def parse_distinguished_name(self) -> list[str]:
        """Parse the distinguished name into its components.

        Returns:
            list[str]: A list of components from the distinguished name.
        """
        return self.distinguishedName.split(',')

    def get_hierarchy(self) -> list[str]:
        """Get the hierarchy of OUs from the root to this OU.

        Returns:
            list[str]: A list of OU names from the root to this OU.
        """
        hierarchy = []
        parts = self.parse_distinguished_name()
        for part in parts:
            if part.startswith('OU='):
                hierarchy.insert(0, part[3:])
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
            'managedBy', 'l', 'streetAddress', 'postalCode', 'telephoneNumber'
        ]
