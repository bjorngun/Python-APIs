import logging

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker


class SQLConnection:
    def __init__(self, server, database, driver):

        self.server = server
        self.database = database
        self.driver = driver
        self.engine = create_engine((
            f"mssql+pyodbc://@{self.server}"
            f"/{self.database}"
            f"?driver={self.driver}"
            "&Trusted_Connection=yes"
            "&TrustServerCertificate=yes"
        ))
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.logger = logging.getLogger(__name__)
        
    def __str__(self):
        return f"SQLConnection(server='{self.server}', database='{self.database}', driver='{self.driver}')"

    def update(self, rows: list):
        """
        Update the specified rows in the database.

        Args:
            updated_list (list): A list of altered rows to update.

        Returns:
            bool: True if the update is successful, False otherwise.
        """
        try:
            for row in rows:
                self.session.merge(row)
            self.session.commit()
            return True
        except SQLAlchemyError as error:
            self.session.rollback()
            self.logger.error('Failed to update rows: %s', error)
            return False
        
    def add(self, new_list: list):
        self.session.add_all(new_list)
