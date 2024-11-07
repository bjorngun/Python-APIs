"""
This module defines the `Employee` class, representing employee data with properties
and methods for generating formatted names and email addresses. The `Employee` class
extends the SQLAlchemy `Base` model, enabling interaction with a database table
for storing employee details.

The environment variables `EMPLOYEE_DB_TABLE` and `EMPLOYEE_DB_SCHEMA` can be set
to customize the table name and schema used for the `Employee` model.
"""

from os import getenv
from typing import Optional, ClassVar

from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, Boolean
from unidecode import unidecode

from python_apis.models.base import Base

load_dotenv()

class Employee(Base):
    """
    Represents an employee with attributes loaded from a database.
    Provides properties and methods for formatted employee data, including
    full name, department, and email generation based on specific formatting rules.
    """

    __tablename__ = getenv('EMPLOYEE_DB_TABLE', 'Employee')
    __table_args__ = {'schema': getenv('EMPLOYEE_DB_SCHEMA', 'DW')}

    # Database columns
    SAP_Id = Column(Integer, primary_key=True)
    SAP_Full_Name = Column(String, nullable=False)
    SAP_Kennitala = Column(String, nullable=False)
    SAP_Department_NO_str = Column(String, nullable=True)
    SAP_Pos = Column(String, nullable=True)
    SAP_Department = Column(String, nullable=True)
    SAP_MainJob = Column(Boolean)
    AD_name = Column(String, nullable=True)
    AD_displayName = Column(String, nullable=True)
    AD_email = Column(String, nullable=True)
    supervisor_distinguishedName = Column(String, nullable=True)
    VIN_Svid = Column(String, nullable=True)
    Thjod_Kyn = Column(String, nullable=True)
    mfld = Column('CSV_MálaflokkurDeild kóti', String, nullable=True)
    firstOrgUnitTelephoneNumber = Column(String, nullable=True)
    firstOrgUnitStreet = Column(String, nullable=True)
    firstOrgUnitPostalCode = Column(String, nullable=True)
    Main_Department = Column(String, nullable=True)
    Main_MFLD_and_Department = Column(String, nullable=True)

    # Non-database fields (annotated with ClassVar)
    name_count: ClassVar[Optional[int]] = None
    multiple: ClassVar[bool] = False

    def __repr__(self) -> str:
        """Returns a string representation of the Employee instance."""
        return f'Employee({self.SAP_Id}-{self.SAP_Full_Name}-{self.SAP_Pos}-{self.SAP_Department})'

    @property
    def employee_number(self) -> str:
        """Returns the employee's SAP ID as a string."""
        return str(self.SAP_Id)

    @property
    def name(self) -> str:
        """
        Returns the preferred name of the employee, prioritizing the Active Directory name
        if available, otherwise falling back to the SAP full name.
        """
        return self.AD_name or self.SAP_Full_Name

    @property
    def first_name(self) -> str:
        """Extracts and returns the employee's first name from the full name."""
        return self.name.split(' ')[0]

    @property
    def display_name(self) -> str:
        """
        Returns a formatted display name. If the position is available,
        it adds a lowercase version of the position title; otherwise, returns
        the Active Directory display name.
        """
        if self.SAP_Pos:
            title = f'{self.SAP_Pos[0].lower()}{self.SAP_Pos[1:]}'
            return f'{self.name} - {title}'
        return self.AD_displayName

    @property
    def ascii_name_dotted(self) -> str:
        """
        Returns a dotted lowercase ASCII-only version of the full name,
        replacing special characters with ASCII equivalents.
        """
        dotted_full_name = '.'.join(self.name.split()).replace('..', '.').strip('.')
        return unidecode(dotted_full_name).lower()

    @property
    def new_mail(self) -> str:
        """
        Generates and returns a new email address for the employee based on
        their ASCII-only, dotted full name and department information, if available.
        The email format is customized to ensure uniqueness in case of duplicates.
        """
        mail = self.ascii_name_dotted
        if f'{mail}@kopavogur.is' not in self.AD_email and self.multiple and self.SAP_Department:
            mail += f'.{unidecode(self.SAP_Department).lower()}'
        return f'{mail}@kopavogur.is'
