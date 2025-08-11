"""
This module defines the `Employee` class, representing employee data with properties
and methods for generating formatted names and email addresses. The `Employee` class
extends the SQLAlchemy `Base` model, enabling interaction with a database table
for storing employee details.

The environment variables `EMPLOYEE_DB_TABLE` and `EMPLOYEE_DB_SCHEMA` can be set
to customize the table name and schema used for the `Employee` model.
"""
from sqlalchemy.orm import declarative_base

Base = declarative_base()
