"""SQLAlchemy model for representing Jira request types."""

from sqlalchemy import Column, Integer, String, Text
from python_apis.models.base import Base


class JiraRequestType(Base):  # pylint: disable=too-few-public-methods
    """
    Jira Request Type model representing request types in the database.

    This model maps the default fields returned by the Jira Service Management API.
    """

    __tablename__ = 'JiraRequestType'

    id = Column(Integer, primary_key=True)  # Request Type numeric ID
    name = Column(String(255), nullable=False)  # Request Type name
    description = Column(Text, nullable=True)  # Request Type description
    help_text = Column(String(1023), nullable=True)  # Help text for the request type
    service_desk_id = Column(Integer, nullable=False)  # ID of the associated Service Desk

    def __repr__(self):
        """
        Return a string representation of the JiraRequestType instance.

        The representation includes the request type's ID, name, and associated service desk ID.

        Returns:
            str: A string in the format 
                "JiraRequestType(id=<id>, name=<name>, service_desk_id=<service_desk_id>)".
        """
        return (
            f"JiraRequestType(id={self.id}, "
            f"name={self.name}, "
            f"service_desk_id={self.service_desk_id})"
        )
