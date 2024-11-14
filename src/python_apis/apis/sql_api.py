"""
Module: sql_api

Provides the `SQLConnection` class for interacting with a SQL database using SQLAlchemy.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker


class SQLConnection:
    """A class to manage SQL database connections and operations using SQLAlchemy."""

    def __init__(self, server: str, database: str, driver: str):
        """
        Initialize the SQLConnection with the given server, database, and driver.

        Args:
            server (str): The server address.
            database (str): The database name.
            driver (str): The ODBC driver name.
        """
        self.logger = logging.getLogger(__name__)
        self.server = server
        self.database = database
        self.driver = driver
        self.engine = create_engine(
            (
                f"mssql+pyodbc://@{self.server}"
                f"/{self.database}"
                f"?driver={self.driver}"
                "&Trusted_Connection=yes"
                "&TrustServerCertificate=yes"
            )
        )
        session_factory = sessionmaker(bind=self.engine)
        self.session = session_factory()

    def __str__(self):
        """Return a string representation of the SQLConnection instance."""
        return (
            f"SQLConnection(server='{self.server}', "
            f"database='{self.database}', "
            f"driver='{self.driver}')"
        )

    def update(self, rows: list) -> bool:
        """
        Update the specified rows in the database.

        Args:
            rows (list): A list of altered rows to update.

        Returns:
            bool: True if the update is successful, raise SQLAlchemyError otherwise.
        """
        try:
            for row in rows:
                self.session.merge(row)
            self.session.commit()
            self.logger.info('JiraIssue table has been successfully updated')
            return True
        except SQLAlchemyError as error:
            self.session.rollback()
            self.logger.error('Failed to update rows: %s', error)
            raise error

    def add(self, new_list: list):
        """
        Add a list of new rows to the database session.

        Args:
            new_list (list): A list of new rows to add.
        """
        self.session.add_all(new_list)
