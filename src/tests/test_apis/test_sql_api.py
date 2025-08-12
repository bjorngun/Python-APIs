import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

# Module under test
from python_apis.apis.sql_api import SQLConnection


class TestSQLConnection(unittest.TestCase):
    def setUp(self):
        # Patch engine + sessionmaker in the module under test
        self.patcher_engine = patch('python_apis.apis.sql_api.create_engine')
        self.patcher_sessionmaker = patch('python_apis.apis.sql_api.sessionmaker')

        self.mock_create_engine = self.patcher_engine.start()
        self.mock_sessionmaker = self.patcher_sessionmaker.start()
        self.addCleanup(self.patcher_engine.stop)
        self.addCleanup(self.patcher_sessionmaker.stop)

        # --- Session factory & session objects ---

        # Backward-compatible default session instance (returned by SessionLocal())
        self.mock_legacy_session = MagicMock(name="legacy_session")

        # Context-managed session used inside update()/add() via SessionLocal.begin()
        self.mock_tx_session = MagicMock(name="tx_session")

        # Context manager returned by SessionLocal.begin()
        self.mock_begin_ctx = MagicMock(name="begin_ctx")
        self.mock_begin_ctx.__enter__.return_value = self.mock_tx_session

        # First call to sessionmaker(...) -> default Session factory (SessionLocal)
        # - calling factory() should return the legacy session (for sql_conn.session)
        # - factory.begin() should return our context manager
        self.MockSessionFactory_Default = MagicMock(name="SessionFactory_Default")
        self.MockSessionFactory_Default.return_value = self.mock_legacy_session
        self.MockSessionFactory_Default.begin.return_value = self.mock_begin_ctx

        # Second call to sessionmaker(...) -> optimized Session factory (SessionOptimized)
        self.MockSessionFactory_Optimized = MagicMock(name="SessionFactory_Optimized")

        # sessionmaker() is called twice in __init__, so return default then optimized
        self.mock_sessionmaker.side_effect = [
            self.MockSessionFactory_Default,
            self.MockSessionFactory_Optimized,
        ]

    def test_init(self):
        # Arrange
        server = 'localhost'
        database = 'test_db'
        driver = 'ODBC Driver 17 for SQL Server'

        # Act
        sql_conn = SQLConnection(server, database, driver)

        # Assert: engine URL + kwargs (fast_executemany/pool_pre_ping/pool_recycle)
        expected_url = (
            f"mssql+pyodbc://@{server}/{database}"
            f"?driver={driver}"
            "&Trusted_Connection=yes"
            "&TrustServerCertificate=yes"
        )
        self.mock_create_engine.assert_called_once_with(
            expected_url,
            fast_executemany=True,
            pool_pre_ping=True,
            pool_recycle=1800,
        )

        # sessionmaker called twice: default + optimized
        self.assertEqual(self.mock_sessionmaker.call_count, 2)
        # First call gets just bind=
        first_call_args, first_call_kwargs = self.mock_sessionmaker.call_args_list[0]
        self.assertIn('bind', first_call_kwargs)
        self.assertEqual(first_call_kwargs['bind'], self.mock_create_engine.return_value)

        # Second call should include our optimized kwargs
        second_call_args, second_call_kwargs = self.mock_sessionmaker.call_args_list[1]
        self.assertIn('bind', second_call_kwargs)
        self.assertEqual(second_call_kwargs['bind'], self.mock_create_engine.return_value)
        self.assertIn('autoflush', second_call_kwargs)
        self.assertFalse(second_call_kwargs['autoflush'])
        self.assertIn('expire_on_commit', second_call_kwargs)
        self.assertFalse(second_call_kwargs['expire_on_commit'])

        # Backward-compat: self.session is created from the default factory()
        self.MockSessionFactory_Default.assert_called_once()
        self.assertIs(sql_conn.session, self.mock_legacy_session)

    def test_update_success(self):
        # Arrange
        sql_conn = SQLConnection('localhost', 'db', 'ODBC Driver 17 for SQL Server')
        row1 = MagicMock()
        row2 = MagicMock()
        rows = [row1, row2]

        # Act
        result = sql_conn.update(rows)

        # Assert: merge called on the transactional session returned by begin()
        self.MockSessionFactory_Default.begin.assert_called_once()
        self.assertEqual(self.mock_tx_session.merge.call_count, 2)
        self.mock_tx_session.merge.assert_any_call(row1)
        self.mock_tx_session.merge.assert_any_call(row2)
        # Commit is handled by the context manager exit in session_scope; update() returns True
        self.assertTrue(result)

    def test_update_failure(self):
        # Arrange
        sql_conn = SQLConnection('localhost', 'db', 'ODBC Driver 17 for SQL Server')
        rows = [MagicMock()]
        # Raise inside the context-managed session
        self.mock_tx_session.merge.side_effect = SQLAlchemyError('Database error')

        # Act / Assert
        with self.assertRaises(SQLAlchemyError):
            sql_conn.update(rows)

        # Ensure we attempted a merge and performed rollback on the tx session
        self.MockSessionFactory_Default.begin.assert_called_once()
        self.mock_tx_session.merge.assert_called_once_with(rows[0])
        self.mock_tx_session.rollback.assert_called_once()

    def test_add(self):
        # Arrange
        sql_conn = SQLConnection('localhost', 'db', 'ODBC Driver 17 for SQL Server')
        row1 = MagicMock()
        row2 = MagicMock()
        new_list = [row1, row2]

        # Act
        sql_conn.add(new_list)

        # Assert: add_all called on the transactional session returned by begin()
        self.MockSessionFactory_Default.begin.assert_called_once()
        self.mock_tx_session.add_all.assert_called_once_with(new_list)


if __name__ == '__main__':
    unittest.main()
