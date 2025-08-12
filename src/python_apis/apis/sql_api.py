"""
Module: sql_api

Provides the `SQLConnection` class for interacting with a SQL database using SQLAlchemy.
Backwards compatible: `self.session` remains available and behaves the same.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


class SQLConnection:
    """Manage SQL Server connections and sessions using SQLAlchemy (pyodbc)."""

    def __init__(self, server: str, database: str, driver: str):
        """
        Initialize the SQLConnection with the given server, database, and driver.

        Args:
            server: The SQL Server host (e.g., 'MYHOST\\SQLEXPRESS' or 'tcp:myhost,1433').
            database: The database name.
            driver: The ODBC driver name (e.g., 'ODBC Driver 17 for SQL Server').
        """
        self.logger = logging.getLogger(__name__)

        # Build the URL (Windows auth).
        self.connection_url = (
            f"mssql+pyodbc://@{server}/{database}"
            f"?driver={driver}"
            "&Trusted_Connection=yes"
            "&TrustServerCertificate=yes"
            # "&MARS_Connection=yes"
        )

        # Engine with fast executemany for bulk operations
        self.engine = create_engine(
            self.connection_url,
            fast_executemany=True,
            pool_pre_ping=True,
            pool_recycle=1800,
        )

        # Default session factory (same defaults as before)
        self.session_local_factory = sessionmaker(bind=self.engine)

        # Optimized session factory for bulk jobs (optional use)
        self.session_optimized_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

        # BACKWARD COMPAT: keep a long-lived session attribute for existing scripts
        self.session: Session = self.session_local_factory()

    def __str__(self) -> str:
        return f"SQLConnection(url='{self.connection_url}')"

    # ---------- Preferred helpers for new code ----------

    def new_session(self) -> Session:
        """Get a new *default* session (same behavior as legacy `self.session`)."""
        return self.session_local_factory()

    def bulk_session(self) -> Session:
        """
        Get a new *optimized* session for bulk work:
        - autoflush disabled (call flush/commit yourself)
        - expire_on_commit disabled (no reloading after commit)
        """
        return self.session_optimized_factory()

    @contextmanager
    def session_scope(self, optimized: bool = False) -> Iterator[Session]:
        """
        Context-managed session. Use `optimized=True` for bulk paths.

        Example:
            with sql.session_scope(optimized=True) as s:
                s.execute(insert(...), payload)
        """
        session_factory = self.session_optimized_factory
        if not optimized:
            session_factory = self.session_local_factory
        s = session_factory()
        try:
            yield s
            s.commit()
        except SQLAlchemyError as err:
            s.rollback()
            raise err
        finally:
            s.close()

    # ---------- Legacy convenience methods (API unchanged) ----------

    def update(self, rows: list) -> bool:
        """
        Update the specified rows in the database.

        Args:
            rows: A list of altered ORM rows to update via merge.
        Returns:
            True if the update succeeds; raises SQLAlchemyError on failure.
        """
        # Use the factory's context manager so tests can assert factory.begin() usage
        s: Session | None = None
        try:
            # Pylint doesn't know sessionmaker has .begin(), but SQLAlchemy 1.4/2.0 does.
            with self.session_local_factory.begin() as s:  # pylint: disable=no-member
                for row in rows:
                    s.merge(row)
            self.logger.info("Rows have been successfully updated")
            return True
        except SQLAlchemyError as error:
            if s is not None:
                s.rollback()
            self.logger.error("Failed to update rows: %s", error)
            raise

    def add(self, new_list: list) -> None:
        """
        Add a list of new rows to the database.

        Args:
            new_list: A list of new ORM rows to add.
        """
        # Use the factory's context manager so tests can assert factory.begin() usage
        with self.session_local_factory.begin() as s:  # pylint: disable=no-member
            s.add_all(new_list)
