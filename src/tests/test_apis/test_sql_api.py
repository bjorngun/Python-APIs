import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError
from python_apis.apis.sql_api import SQLConnection

class TestSQLConnection(unittest.TestCase):
    def setUp(self):
        # Mock create_engine and sessionmaker to avoid real database connections
        self.patcher_engine = patch('python_apis.apis.sql_api.create_engine')
        self.patcher_sessionmaker = patch('python_apis.apis.sql_api.sessionmaker')
        self.mock_create_engine = self.patcher_engine.start()
        self.mock_sessionmaker = self.patcher_sessionmaker.start()
        self.addCleanup(self.patcher_engine.stop)
        self.addCleanup(self.patcher_sessionmaker.stop)

        # Mock the session object
        self.mock_session = MagicMock()
        # Mock Session class
        self.MockSessionClass = MagicMock(return_value=self.mock_session)
        self.mock_sessionmaker.return_value = self.MockSessionClass

    def test_init(self):
        # Arrange
        server = 'localhost'
        database = 'test_db'
        driver = 'ODBC Driver 17 for SQL Server'
        
        # Act
        sql_conn = SQLConnection(server, database, driver)
        
        # Assert
        expected_connection_string = (f"mssql+pyodbc://@{server}/{database}"
                                      f"?driver={driver}"
                                      "&Trusted_Connection=yes"
                                      "&TrustServerCertificate=yes")
        self.mock_create_engine.assert_called_once_with(expected_connection_string)
        self.mock_sessionmaker.assert_called_once_with(bind=self.mock_create_engine.return_value)
        self.MockSessionClass.assert_called_once()
        self.assertEqual(sql_conn.session, self.mock_session)

    def test_update_success(self):
        # Arrange
        sql_conn = SQLConnection('driver', 'server', 'database')
        row1 = MagicMock()
        row2 = MagicMock()
        rows = [row1, row2]
        
        # Act
        result = sql_conn.update(rows)
        
        # Assert
        self.mock_session.merge.assert_any_call(row1)
        self.mock_session.merge.assert_any_call(row2)
        self.assertEqual(self.mock_session.merge.call_count, 2)
        self.mock_session.commit.assert_called_once()
        self.assertTrue(result)

    def test_update_failure(self):
        # Arrange
        sql_conn = SQLConnection('driver', 'server', 'database')
        rows = [MagicMock()]
        sql_conn.session.merge.side_effect = SQLAlchemyError('Database error')

        with self.assertRaises(SQLAlchemyError):
            sql_conn.update(rows)
        # row = MagicMock()
        # rows = [row]
        # self.mock_session.merge.side_effect = SQLAlchemyError('Database error')
        
        # # Act
        # result = sql_conn.update(rows)
        
        # # Assert
        # self.mock_session.merge.assert_called_once_with(row)
        # self.mock_session.rollback.assert_called_once()
        # self.mock_session.commit.assert_not_called()
        # self.assertFalse(result)

    def test_add(self):
        # Arrange
        sql_conn = SQLConnection('driver', 'server', 'database')
        row1 = MagicMock()
        row2 = MagicMock()
        new_list = [row1, row2]
        
        # Act
        sql_conn.add(new_list)
        
        # Assert
        self.mock_session.add_all.assert_called_once_with(new_list)

if __name__ == '__main__':
    unittest.main()
