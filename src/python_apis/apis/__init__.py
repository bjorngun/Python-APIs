"""
Module: apis

This package provides classes for connecting to and interacting with external APIs, specifically
Active Directory and SQL databases.

Available Classes:
    - ADConnection: Facilitates connection and operations with Active Directory services.
    - SQLConnection: Manages SQL database connections and operations using SQLAlchemy.

Usage Example:
    from apis import ADConnection, SQLConnection

    # Active Directory Connection
    ad_connection = ADConnection(
        servers=['ldap://server1', 'ldap://server2'],
        base_dn='dc=example,dc=com'
    )
    ad_users = ad_connection.search('(objectClass=user)')

    # SQL Database Connection
    sql_connection = SQLConnection(
        server='db_server',
        database='db_name',
        driver='ODBC Driver 17 for SQL Server'
    )
    sql_session = sql_connection.session
    # Perform database operations using sql_session

Notes:
    - The `ADConnection` class handles LDAP operations for querying and modifying
        Active Directory entries.
    - The `SQLConnection` class provides an SQLAlchemy session for database interactions.

Dependencies:
    - Requires the `ldap3` library for LDAP operations.
    - Requires `SQLAlchemy` for database ORM functionality.

"""

from python_apis.apis.ad_api import ADConnection
from python_apis.apis.jira_api import JiraConnection
from python_apis.apis.sql_api import SQLConnection

__all__ = [
    "ADConnection",
    "JiraConnection",
    "SQLConnection",
]
