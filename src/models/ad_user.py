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
    user = session.query(ADUser).filter_by(sam_account_name='jdoe').first()

    # Access user attributes
    print(user.display_name)
    print(user.email)

    # Use property methods
    print(user.smtp_address)
    print(user.can_change)

    # Close the session
    session.close()

Notes:
    - Field Naming: The class attributes are named using `snake_case` to comply with PEP 8
      conventions. If the database column names differ, the `Column` definitions specify the
      exact column names using the `name` parameter.
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
from sqlalchemy.orm import validates

from models.base import Base


class ADUser(Base):
    """Active Directory User model representing user attributes in the database."""

    __tablename__ = 'ADUser'

    account_expires = Column(DATETIME2, nullable=True)
    bad_password_time = Column(DATETIME2, nullable=True)
    bad_pwd_count = Column(String(256))
    cn = Column(String(256))
    code_page = Column(String(256))
    company = Column(String(256))
    country_code = Column(String(256))
    department = Column(String(256))
    department_number = Column(String(256))
    description = Column(String(1024))
    display_name = Column(String(256))
    distinguished_name = Column(String(255), primary_key=True)
    division = Column(String(256))
    employee_id = Column(String(256), nullable=False)
    employee_number = Column(String(256))
    extension_attribute1 = Column(String(256))
    extension_attribute2 = Column(String(256))
    extension_attribute3 = Column(String(256))
    extension_attribute4 = Column(String(256))
    extension_attribute5 = Column(String(256))
    extension_attribute6 = Column(String(256))
    extension_attribute7 = Column(String(256))
    extension_attribute8 = Column(String(256))
    extension_attribute9 = Column(String(256))
    extension_attribute10 = Column(String(256))
    extension_attribute11 = Column(String(256))
    extension_attribute12 = Column(String(256))
    extension_attribute13 = Column(String(256))
    extension_attribute14 = Column(String(256))
    extension_attribute15 = Column(String(256))
    given_name = Column(String(256))
    home_mdb = Column(String(256))
    home_phone = Column(String(256))
    instance_type = Column(String(256))
    locality_name = Column(String(256))  # Renamed from 'l'
    last_logon = Column(DATETIME2, nullable=True)
    last_logon_timestamp = Column(DATETIME2, nullable=True)
    legacy_exchange_dn = Column(String(256))
    lockout_time = Column(DATETIME2, nullable=True)
    logon_count = Column(String(256))
    mail = Column(String(256))
    mail_nickname = Column(String(256))
    manager = Column(String(256))
    mdb_use_defaults = Column(String(256))
    mobile = Column(String(256))
    name = Column(String(256))
    object_category = Column(String(256))
    object_class = Column(String(256))
    object_guid = Column(String(256))
    object_sid = Column(String(256))
    physical_delivery_office_name = Column(String(256))
    postal_code = Column(String(256))
    primary_group_id = Column(String(256))
    protocol_settings = Column(String(256))
    proxy_addresses = Column(String(2048))
    pwd_last_set = Column(DATETIME2, nullable=True)
    sam_account_name = Column(String(256))
    sam_account_type = Column(String(256))
    sn = Column(String(256))
    street_address = Column(String(256))
    facsimile_telephone_number = Column(String(256))
    postal_address = Column(String(256))
    telephone_number = Column(String(256))
    text_encoded_or_address = Column(String(256))
    title = Column(String(256))
    user_account_control = Column(String(256))
    user_principal_name = Column(String(256))
    usn_changed = Column(Integer)
    usn_created = Column(Integer)
    when_changed = Column(DATETIME2, nullable=True)
    when_created = Column(DATETIME2, nullable=True)
    ou = Column(String(256))

    first_org_unit_description = Column(String(256))
    first_org_unit_telephone_number = Column(String(256))
    first_org_unit_street = Column(String(256))
    first_org_unit_postal_code = Column(String(256))
    enabled = Column(Boolean)

    # Non-database field
    changes: ClassVar[Optional[str]] = None

    def __repr__(self) -> str:
        """Return a string representation of the ADUser instance."""
        return f"ADUser({self.employee_number}-{self.display_name}-{self.department})"

    @property
    def proxy_address_list(self) -> list[str]:
        """Return the proxy addresses as a list.

        Splits the `proxy_addresses` string by commas and strips whitespace.

        Returns:
            list[str]: A list of proxy addresses.
        """
        if self.proxy_addresses:
            return [x.strip() for x in self.proxy_addresses.split(',')]
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
        return self.extension_attribute7 != '1'

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

    @validates("department_number")
    def validate_department_number(self, _key: str, department_number) -> Optional[str]:
        """Validate and process the `department_number` field.

        Ensures the value is a string or None.

        Args:
            key (str): The name of the field being validated.
            department_number: The value to validate.

        Returns:
            Optional[str]: The validated department number.
        """
        if isinstance(department_number, list):
            department_number = department_number[0] if department_number else None
        return department_number

    @validates("proxy_addresses")
    def validate_proxy_addresses(self, _key: str, proxy_addresses) -> Optional[str]:
        """Validate and process the `proxy_addresses` field.

        Converts a list to a comma-separated string.

        Args:
            key (str): The name of the field being validated.
            proxy_addresses: The value to validate.

        Returns:
            Optional[str]: The validated proxy addresses.
        """
        if isinstance(proxy_addresses, list):
            proxy_addresses = ','.join(proxy_addresses) if proxy_addresses else None
        return proxy_addresses

    @validates("description")
    def validate_description(self, _key: str, description) -> Optional[str]:
        """Validate and process the `description` field.

        Converts a list to a comma-separated string.

        Args:
            key (str): The name of the field being validated.
            description: The value to validate.

        Returns:
            Optional[str]: The validated description.
        """
        if isinstance(description, list):
            description = ','.join(description) if description else None
        return description

    @validates("object_class")
    def validate_object_class(self, _key: str, object_class) -> Optional[str]:
        """Validate and process the `object_class` field.

        Converts a list to a comma-separated string.

        Args:
            key (str): The name of the field being validated.
            object_class: The value to validate.

        Returns:
            Optional[str]: The validated object class.
        """
        if isinstance(object_class, list):
            object_class = ','.join(object_class) if object_class else None
        return object_class

    @validates("extension_attribute7")
    def validate_extension_attribute7(self, _key: str, extension_attribute7) -> Optional[str]:
        """Validate and process the `extension_attribute7` field.

        Converts a list to a comma-separated string.

        Args:
            key (str): The name of the field being validated.
            extension_attribute7: The value to validate.

        Returns:
            Optional[str]: The validated extension attribute 7.
        """
        if isinstance(extension_attribute7, list):
            extension_attribute7 = ','.join(extension_attribute7) if extension_attribute7 else None
        return extension_attribute7

    @validates("distinguished_name")
    def validate_distinguished_name(self, _key: str, distinguished_name: str) -> str:
        """Validate and process the `distinguished_name` field.

        Extracts the organizational unit (OU) from the distinguished name.

        Args:
            key (str): The name of the field being validated.
            distinguished_name (str): The distinguished name to validate.

        Returns:
            str: The validated distinguished name.
        """
        self.ou = ','.join(distinguished_name.split(',')[1:])
        return distinguished_name

    @validates("user_account_control")
    def validate_user_account_control(self, _key: str, user_account_control) -> str:
        """Validate and process the `user_account_control` field.

        Determines if the account is enabled based on the control flags.

        Args:
            key (str): The name of the field being validated.
            user_account_control: The value to validate.

        Returns:
            str: The validated user account control.
        """
        self.enabled = (int(user_account_control) & 2) == 0
        return user_account_control

    @validates("lockout_time")
    def validate_lockout_time(self, _key: str, lockout_time) -> Optional[DATETIME2]:
        """Validate and process the `lockout_time` field.

        Normalizes the lockout time value.

        Args:
            key (str): The name of the field being validated.
            lockout_time: The value to validate.

        Returns:
            Optional[DATETIME2]: The validated lockout time.
        """
        if isinstance(lockout_time, list):
            lockout_time = lockout_time[0] if lockout_time else None

        if lockout_time is not None:
            lockout_time = lockout_time.replace(tzinfo=None)
        return lockout_time

    @validates("account_expires")
    def validate_account_expires(self, _key: str, account_expires) -> Optional[DATETIME2]:
        """Validate and process the `account_expires` field.

        Normalizes the account expiration date.

        Args:
            key (str): The name of the field being validated.
            account_expires: The value to validate.

        Returns:
            Optional[DATETIME2]: The validated account expiration date.
        """
        if isinstance(account_expires, list):
            account_expires = account_expires[0] if account_expires else None

        if account_expires is not None:
            account_expires = account_expires.replace(tzinfo=None)
        return account_expires

    @validates("bad_password_time")
    def validate_bad_password_time(self, _key: str, bad_password_time) -> Optional[DATETIME2]:
        """Validate and process the `bad_password_time` field.

        Normalizes the bad password time value.

        Args:
            key (str): The name of the field being validated.
            bad_password_time: The value to validate.

        Returns:
            Optional[DATETIME2]: The validated bad password time.
        """
        if isinstance(bad_password_time, list):
            bad_password_time = bad_password_time[0] if bad_password_time else None

        if bad_password_time is not None:
            bad_password_time = bad_password_time.replace(tzinfo=None)
        return bad_password_time

    @validates("last_logon")
    def validate_last_logon(self, _key: str, last_logon) -> Optional[DATETIME2]:
        """Validate and process the `last_logon` field.

        Normalizes the last logon time.

        Args:
            key (str): The name of the field being validated.
            last_logon: The value to validate.

        Returns:
            Optional[DATETIME2]: The validated last logon time.
        """
        if isinstance(last_logon, list):
            last_logon = last_logon[0] if last_logon else None

        if last_logon is not None:
            last_logon = last_logon.replace(tzinfo=None)
        return last_logon

    @validates("pwd_last_set")
    def validate_pwd_last_set(self, _key: str, pwd_last_set) -> Optional[DATETIME2]:
        """Validate and process the `pwd_last_set` field.

        Normalizes the password last set time.

        Args:
            key (str): The name of the field being validated.
            pwd_last_set: The value to validate.

        Returns:
            Optional[DATETIME2]: The validated password last set time.
        """
        if isinstance(pwd_last_set, list):
            pwd_last_set = pwd_last_set[0] if pwd_last_set else None

        if pwd_last_set is not None:
            pwd_last_set = pwd_last_set.replace(tzinfo=None)
        return pwd_last_set

    @validates("when_changed")
    def validate_when_changed(self, _key: str, when_changed) -> Optional[DATETIME2]:
        """Validate and process the `when_changed` field.

        Normalizes the when changed timestamp.

        Args:
            key (str): The name of the field being validated.
            when_changed: The value to validate.

        Returns:
            Optional[DATETIME2]: The validated when changed timestamp.
        """
        if isinstance(when_changed, list):
            when_changed = when_changed[0] if when_changed else None

        if when_changed is not None:
            when_changed = when_changed.replace(tzinfo=None)
        return when_changed

    @validates("when_created")
    def validate_when_created(self, _key: str, when_created) -> Optional[DATETIME2]:
        """Validate and process the `when_created` field.

        Normalizes the when created timestamp.

        Args:
            key (str): The name of the field being validated.
            when_created: The value to validate.

        Returns:
            Optional[DATETIME2]: The validated when created timestamp.
        """
        if isinstance(when_created, list):
            when_created = when_created[0] if when_created else None

        if when_created is not None:
            when_created = when_created.replace(tzinfo=None)
        return when_created

    @validates("last_logon_timestamp")
    def validate_last_logon_timestamp(self, _key: str, last_logon_timestamp) -> Optional[DATETIME2]:
        """Validate and process the `last_logon_timestamp` field.

        Normalizes the last logon timestamp.

        Args:
            key (str): The name of the field being validated.
            last_logon_timestamp: The value to validate.

        Returns:
            Optional[DATETIME2]: The validated last logon timestamp.
        """
        if isinstance(last_logon_timestamp, list):
            last_logon_timestamp = last_logon_timestamp[0] if last_logon_timestamp else None

        if last_logon_timestamp is not None:
            last_logon_timestamp = last_logon_timestamp.replace(tzinfo=None)
        return last_logon_timestamp

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
