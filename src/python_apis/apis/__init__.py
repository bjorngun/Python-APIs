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

# pylint: disable=duplicate-code

from python_apis.apis.ad_config import ADAuthenticationMode, ADTLSConfig
from python_apis.apis.ad_api import (
    ADConnection,
    AD_RECOVERABLE_READ_EXCEPTIONS,
    AD_READ_RETRY_POLICY,
    AD_WRITE_RETRY_POLICY,
    RetryTelemetry,
    escape_filter_value,
)
from python_apis.apis.ad_errors import (
    ADBindError,
    ADConfigurationError,
    ADConnectionError,
    ADMalformedQueryError,
    ADMalformedResultError,
    ADMissingServersError,
    ADQueryRejectedError,
    ADReadError,
    ADSearchError,
    ADTimeoutError,
    ADTLSConfigurationError,
    ADTLSVerificationError,
    ADTransportError,
)
from python_apis.apis.jira_api import JiraConnection
from python_apis.apis.sql_api import SQLConnection

__all__ = [
    "ADAuthenticationMode",
    "ADBindError",
    "ADConfigurationError",
    "ADConnection",
    "ADConnectionError",
    "ADMalformedQueryError",
    "ADMalformedResultError",
    "ADMissingServersError",
    "ADQueryRejectedError",
    "ADReadError",
    "AD_RECOVERABLE_READ_EXCEPTIONS",
    "AD_READ_RETRY_POLICY",
    "AD_WRITE_RETRY_POLICY",
    "ADSearchError",
    "ADTimeoutError",
    "ADTLSConfig",
    "ADTLSConfigurationError",
    "ADTLSVerificationError",
    "ADTransportError",
    "RetryTelemetry",
    "escape_filter_value",
    "JiraConnection",
    "SQLConnection",
]
