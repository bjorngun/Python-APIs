from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import validates
from models.base import Base
from typing import Optional, ClassVar

class ADUser(Base):
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
    
    # Non-database field (annotated with ClassVar)
    changes: ClassVar[Optional[str]] = None
    
    def __repr__(self) -> str:
        return f'ADUser({self.employeeNumber}-{self.displayName}-{self.department})'

    @property
    def proxy_address_list(self) -> list[str]:
        """Return the proxy addresses as a list."""
        if self.proxyAddresses:
            return [x.strip() for x in self.proxyAddresses.split(',')]
        else:
            return []

    @property
    def SMTP_address(self) -> Optional[str]:
        """Return the primary SMTP address."""
        for address in self.proxy_address_list:
            if address.startswith('SMTP:'):
                return address
        return None

    @property
    def can_change(self) -> bool:
        """Determine if the user can change settings based on extensionAttribute7."""
        return self.extensionAttribute7 != '1'

    def proxyAddresses_with_new_SMTP(self, new_SMTP: str) -> list[str]:
        """Generate a new list of proxy addresses with a new primary SMTP address.

        Args:
            new_SMTP (str): The new primary SMTP email address.

        Returns:
            List[str]: Updated list of proxy addresses.
        """
        updated_addresses = []

        if self.SMTP_address and new_SMTP in self.SMTP_address:
            return self.proxy_address_list

        new_SMTP_full = f'SMTP:{new_SMTP}'
        for address in self.proxy_address_list:
            if address.lower() == new_SMTP_full.lower():
                continue

            if address.startswith('SMTP:'):
                # Convert existing primary SMTP to secondary
                updated_addresses.append('smtp:' + address[5:])
            else:
                # Keep all other addresses
                updated_addresses.append(address)

        # Add the new primary SMTP
        updated_addresses.append(new_SMTP_full)
        return updated_addresses

    @validates("departmentNumber")
    def validate_departmentNumber(self, key, departmentNumber) -> str:
        if isinstance(departmentNumber, list):
            if len(departmentNumber) == 0:
                departmentNumber = None
            else:
                departmentNumber = departmentNumber[0]
        return departmentNumber

    @validates("proxyAddresses")
    def validate_proxyAddresses(self, key, proxyAddresses) -> str:
        if isinstance(proxyAddresses, list):
            if len(proxyAddresses) == 0:
                proxyAddresses = None
            else:
                proxyAddresses = ','.join(proxyAddresses)
        return proxyAddresses

    @validates("description")
    def validate_description(self, key, description) -> str:
        if isinstance(description, list):
            if len(description) == 0:
                description = None
            else:
                description = ','.join(description)
        return description

    @validates("objectClass")
    def validate_objectClass(self, key, objectClass) -> str:
        if isinstance(objectClass, list):
            if len(objectClass) == 0:
                objectClass = None
            else:
                objectClass = ','.join(objectClass)
        return objectClass

    @validates("extensionAttribute7")
    def validate_extensionAttribute7(self, key, extensionAttribute7) -> str:
        if isinstance(extensionAttribute7, list):
            if len(extensionAttribute7) == 0:
                extensionAttribute7 = None
            else:
                extensionAttribute7 = ','.join(extensionAttribute7)
        return extensionAttribute7

    @validates("distinguishedName")
    def validate_distinguishedName(self, key, distinguishedName) -> str:
        self.ou = ','.join(distinguishedName.split(',')[1:])
        return distinguishedName

    @validates("userAccountControl")
    def validate_userAccountControl(self, key, userAccountControl) -> bool:
        self.enabled = True if ((userAccountControl & 2) == 0) else False
        return userAccountControl

    @validates("lockoutTime")
    def validate_lockoutTime(self, key, lockoutTime) -> str:
        if isinstance(lockoutTime, list):
            if len(lockoutTime) == 0:
                lockoutTime = None
            else:
                lockoutTime = lockoutTime[0]

        if lockoutTime is not None:
            lockoutTime = lockoutTime.replace(tzinfo=None)
        return lockoutTime

    @validates("accountExpires")
    def validate_accountExpires(self, key, accountExpires) -> str:
        if isinstance(accountExpires, list):
            if len(accountExpires) == 0:
                accountExpires = None
            else:
                accountExpires = accountExpires[0]

        if accountExpires is not None:
            accountExpires = accountExpires.replace(tzinfo=None)
        return accountExpires

    @validates("badPasswordTime")
    def validate_badPasswordTime(self, key, badPasswordTime) -> str:
        if isinstance(badPasswordTime, list):
            if len(badPasswordTime) == 0:
                badPasswordTime = None
            else:
                badPasswordTime = badPasswordTime[0]

        if badPasswordTime is not None:
            badPasswordTime = badPasswordTime.replace(tzinfo=None)
        return badPasswordTime

    @validates("lastLogon")
    def validate_lastLogon(self, key, lastLogon) -> str:
        if isinstance(lastLogon, list):
            if len(lastLogon) == 0:
                lastLogon = None
            else:
                lastLogon = lastLogon[0]

        if lastLogon is not None:
            lastLogon = lastLogon.replace(tzinfo=None)
        return lastLogon

    @validates("accountExpires")
    def validate_accountExpires(self, key, accountExpires) -> str:
        if isinstance(accountExpires, list):
            if len(accountExpires) == 0:
                accountExpires = None
            else:
                accountExpires = accountExpires[0]

        if accountExpires is not None:
            accountExpires = accountExpires.replace(tzinfo=None)
        return accountExpires

    @validates("pwdLastSet")
    def validate_pwdLastSet(self, key, pwdLastSet) -> str:
        if isinstance(pwdLastSet, list):
            if len(pwdLastSet) == 0:
                pwdLastSet = None
            else:
                pwdLastSet = pwdLastSet[0]

        if pwdLastSet is not None:
            pwdLastSet = pwdLastSet.replace(tzinfo=None)
        return pwdLastSet

    @validates("whenChanged")
    def validate_whenChanged(self, key, whenChanged) -> str:
        if isinstance(whenChanged, list):
            if len(whenChanged) == 0:
                whenChanged = None
            else:
                whenChanged = whenChanged[0]

        if whenChanged is not None:
            whenChanged = whenChanged.replace(tzinfo=None)
        return whenChanged

    @validates("whenCreated")
    def validate_whenCreated(self, key, whenCreated) -> str:
        if isinstance(whenCreated, list):
            if len(whenCreated) == 0:
                whenCreated = None
            else:
                whenCreated = whenCreated[0]

        if whenCreated is not None:
            whenCreated = whenCreated.replace(tzinfo=None)
        return whenCreated

    @validates("lastLogonTimestamp")
    def validate_lastLogonTimestamp(self, key, lastLogonTimestamp) -> str:
        if isinstance(lastLogonTimestamp, list):
            if len(lastLogonTimestamp) == 0:
                lastLogonTimestamp = None
            else:
                lastLogonTimestamp = lastLogonTimestamp[0]

        if lastLogonTimestamp is not None:
            lastLogonTimestamp = lastLogonTimestamp.replace(tzinfo=None)
        return lastLogonTimestamp

    def get_attribute_list():
        return ['accountExpires', 'badPasswordTime', 'badPwdCount', 'cn', 'codePage',
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
                'whenCreated']
