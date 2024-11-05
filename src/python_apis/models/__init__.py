"""
Here the models for the Python-APIs package are available, if you are creating a new services
you can import the model from here if it is available.
"""

from python_apis.models.ad_user import ADUser
from python_apis.models.sap_employee import Employee

__all__ = [
    "ADUser",
    "Employee",
]
