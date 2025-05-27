"""
The services provided in this package are mostly examples of how to use the
api's with the models.  I expect in most cases there has to be a custom service
module or a few of them.
"""

# pylint: disable=duplicate-code

from python_apis.services.ad_group_service import ADGroupService
from python_apis.services.ad_user_service import ADUserService
from python_apis.services.ad_ou_service import ADOrganizationalUnitService
from python_apis.services.employee_service import EmployeeService

__all__ = [
    "ADGroupService",
    "ADUserService",
    "ADOrganizationalUnitService",
    "EmployeeService",
]
