"""
The services provided in this package are mostly examples of how to use the
api's with the models.  I expect in most cases there has to be a custom service
module or a few of them.
"""

from python_apis.services.ad_user_service import ADUserService
from python_apis.services.employee_service import EmployeeService

__all__ = [
    "ADUserService",
    "EmployeeService",
]
