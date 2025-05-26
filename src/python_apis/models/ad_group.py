"""
ad_group.py

This module defines the `ADGroup` class, which represents an Active Directory Group in the database.
The `ADGroup` model maps group attributes retrieved from Active Directory to a relational database
using SQLAlchemy.
"""

from typing import Optional, ClassVar
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.mssql import DATETIME2

from .base import Base


class ADGroup(Base):
    """Active Directory Group model representing group attributes in the database."""

    __tablename__ = 'ADGroup'

    cn = Column(String(256), nullable=True)
    description = Column(String(1024), nullable=True)
    distinguishedName = Column(String(255), primary_key=True)
    groupType = Column(Integer, nullable=True)
    groupType_name = Column(String(256), nullable=True)
    instanceType = Column(String(256), nullable=True)
    managedBy = Column(String(256), nullable=True)
    name = Column(String(256))
    objectCategory = Column(String(256), nullable=True)
    objectClass = Column(String(256), nullable=True)
    objectGUID = Column(String(256), nullable=True)
    objectSid = Column(String(256), nullable=True)
    sAMAccountName = Column(String(256), nullable=True)
    sAMAccountType = Column(String(256), nullable=True)
    uSNChanged = Column(Integer, nullable=True)
    uSNCreated = Column(Integer, nullable=True)
    whenChanged = Column(DATETIME2, nullable=True)
    whenCreated = Column(DATETIME2, nullable=True)
    extensionName = Column(Text, nullable=True)
    ou = Column(String(256), nullable=True)

    # Non-database field
    changes: ClassVar[Optional[str]] = None

    def __repr__(self) -> str:
        """Return a string representation of the ADGroup instance."""
        return f"ADGroup({self.name}-{self.description})"

    def get_ou(self):
        ou = ','.join(self.distinguishedName.split(',')[1:])
        return ou

    @property
    def group_type_name(self) -> str:
        '''Get name of type of group for the integer representing the group in AD'''
        GROUP_TYPES = {
            '2': 'Distribution Group - Global',
            '4': 'Distribution Group - Domain Local',
            '8': 'Distribution Group - Universal',
            '-2147483646': 'Security Group - Global',
            '-2147483644': 'Security Group - Domain Local',
            '-2147483643': 'Security Group - Domain Local',
            '-2147483640': 'Security Group - Universal'
        }
        if str(self.groupType) not in GROUP_TYPES:
            return  'N/A'
        return GROUP_TYPES[str(self.groupType)]

    @staticmethod
    def get_attribute_list():
        return [
            'cn',
            'description',
            'distinguishedName',
            'groupType',
            'instanceType',
            'managedBy',
            'name',
            'objectCategory',
            'objectClass',
            'objectGUID',
            'objectSid',
            'sAMAccountName',
            'sAMAccountType',
            'uSNChanged',
            'uSNCreated',
            'whenChanged',
            'whenCreated',
            'extensionName',
        ]
