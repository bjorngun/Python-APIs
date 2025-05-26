"""
Module providing the ADUserService class for interacting with Active Directory users.
"""

from os import getenv

from dev_tools import timing_decorator

from python_apis.apis import SQLConnection
from python_apis.models import Employee

class EmployeeService:
    """Service class for interacting with employees.
    """

    def __init__(self, sql_connection: SQLConnection = None):
        """Initialize the ADUserService with an ADConnection.

        Args:
            sql_connection (SQLConnection, optional): An existing SQLConnection instance.
                If None, a new one will be created.
        """
        if sql_connection is None:
            sql_connection = self._get_sql_connection()
        self.sql_connection = sql_connection

    def _get_sql_connection(self) -> SQLConnection:
        return SQLConnection(
            server=getenv('EMPLOYEE_DB_SERVER', getenv('DEFAULT_DB_SERVER')),
            database=getenv('EMPLOYEE_DB_NAME', getenv('DEFAULT_DB_NAME')),
            driver=getenv('EMPLOYEE_SQL_DRIVER', getenv('DEFAULT_SQL_DRIVER')),
        )

    @timing_decorator
    def get_employees(self) -> list[Employee]:
        """Retrieve employees from database.

        Returns:
            list[Employee]: A list of Employee instances.
        """

        employees = self.sql_connection.session.query(Employee).all()
        return employees

    def get_employee_table_info(self) -> dict:
        """
        Fetches metadata information about the `Employee` table from the database.

        Returns:
            dict: A dictionary containing column names as keys and their data types as values.
        """
        inspector = self.sql_connection.session.bind.dialect.get_columns
        columns_info = inspector(self.sql_connection.engine, Employee.__tablename__)

        table_info = {
            column['name']: column['type'] for column in columns_info
        }

        return table_info
