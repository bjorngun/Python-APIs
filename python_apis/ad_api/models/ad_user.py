from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class ADUser:
    sAMAccountName: str
    distinguishedName: str
    name: Optional[str]
    employeeID: Optional[str]
    employeeNumber: Optional[Any]
    department: Optional[Any]
    division: Optional[Any]
    company: Optional[Any]
    physicalDeliveryOfficeName: Optional[Any]
    telephoneNumber: Optional[Any]
    mobile: Optional[Any]
    mail: Optional[Any]
    manager: Optional[Any]
    memberOf: Optional[Any]
    managedBy: Optional[Any]
    objectClass: Optional[Any]
    objectCategory: Optional[str]
    extensionAttribute7: Optional[Any]
    userAccountControl: Optional[int]

    description: Optional[Any]

    departmentNumber: Optional[Any]
    title: Optional[Any]

    changes: Optional[Any]

    @property
    def departmentNumber_str(self) -> str:
        if isinstance(self.departmentNumber, list):
            if len(self.departmentNumber) == 0:
                return None
            return self.departmentNumber[0]
        return self.departmentNumber

    @property
    def employeeNumber_int(self) -> Optional[int]:
        if isinstance(self.employeeNumber, list):
            if len(self.employeeNumber) == 0:
                return None
            return int(self.employeeNumber[0])
        return int(self.employeeNumber)

    @property
    def title_str(self) -> str:
        if len(self.title) > 0:
            return self.title[0].lower() + self.title[1:]
        return self.title

    @property
    def can_change(self) -> str:
        return self.extensionAttribute7 != '1'

    @staticmethod
    def attributes() -> List[str]:
        return [
            'distinguishedName',
            'name',
            'title',
            'employeeID',
            'employeeNumber',
            'department',
            'division',
            'company',
            'departmentNumber',
            'mail',
            'extensionAttribute7',
            'manager',
            'userAccountControl',
        ]

    @staticmethod
    def attributes_extended() -> List[str]:
        return [
            'sAMAccountName',
            'distinguishedName',
            'name',
            'title',
            'description',
            'employeeID',
            'employeeNumber',
            'department',
            'division',
            'company',
            'departmentNumber',
            'physicalDeliveryOfficeName',
            'telephoneNumber',
            'mobile',
            'mail',
            'extensionAttribute7',
            'manager',
            'memberOf',
            'managedBy',
            'objectClass',
            'objectCategory',
            'userAccountControl',
        ]

    @property
    def enabled(self) -> bool:
        return self.userAccountControl&2 == 0
