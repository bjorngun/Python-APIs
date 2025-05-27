"""
jira_issue.py

This module defines the `JiraIssue` class, which represents a Jira issue in the database.
The `JiraIssue` model maps the default fields returned by the Jira Cloud REST API to a relational
database
using SQLAlchemy.

Classes:
    JiraIssue: A SQLAlchemy model for storing attributes of Jira issues.

Methods:
    __repr__: Returns a string representation of the `JiraIssue` instance.
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text
from python_apis.models.base import Base

class JiraIssue(Base):  # pylint: disable=too-few-public-methods
    """
    Jira Issue model representing issue attributes in the database.

    This model maps the default fields returned by the Jira Cloud REST API to a relational database
    using SQLAlchemy.
    """

    __tablename__ = 'JiraIssue'

    id = Column(Integer, primary_key=True)  # Issue numeric ID
    key = Column(String(255), nullable=False)  # Issue key, e.g., 'UT-124'
    summary = Column(String(1023), nullable=False)  # Issue title
    description = Column(Text, nullable=True)
    status = Column(String(255), nullable=False)  # Status name (e.g., "To Do", "In Progress")
    priority = Column(String(255), nullable=True)  # Priority level
    issue_type = Column('issueType', String(255), nullable=False)
    # Type of the issue (e.g., Bug, Task)

    assignee_display_name = Column('assignee_displayName', String(255), nullable=True)
    assignee_account_id = Column('assignee_accountId', String(255), nullable=True)
    assignee_active = Column(Boolean, nullable=True)

    reporter_display_name = Column('reporter_displayName', String(255), nullable=True)
    reporter_account_id = Column('reporter_accountId', String(255), nullable=True)
    reporter_active = Column(Boolean, nullable=True)
    reporter_email_address = Column(String(255), nullable=True)

    created = Column(DateTime, nullable=False)  # Issue creation time
    updated = Column(DateTime, nullable=False)  # Last updated time
    resolutiondate = Column(DateTime, nullable=False)

    project_key = Column(String(255), nullable=True)  # Project key
    project_name = Column(String(255), nullable=True)  # Project name
    project_id = Column('projectId', String(255), nullable=True)

    request_type_id = Column(String(255), nullable=True)
    request_type_name = Column(String(255), nullable=True)
    request_type_description = Column(String(255), nullable=True)

    parent_id = Column(Integer, nullable=True)  # For sub-tasks
    parent_key = Column(String(255), nullable=True)  # For sub-tasks
    parent_summary = Column(String(255), nullable=True)  # For sub-tasks

    # Custom fields (add more as needed)
    customfield_10116 = Column("Reporter old Company/Department/MFLD", String(255), nullable=True)
    customfield_10117 = Column("Reporter Department Number", String(255), nullable=True)
    customfield_10157 = Column("Kennitala", String(255), nullable=True)
    customfield_10010 = Column("Request Type", String(255), nullable=True)

    customfield_10113 = Column("Working on ticket", String(255), nullable=True)
    customfield_10114 = Column("Sync Request", String(255), nullable=True)
    customfield_10118 = Column("Sensa Assignee", String(255), nullable=True)
    customfield_10120 = Column("External synced issue key", String(255), nullable=True)

    current_status_name = Column(String(255), nullable=True)
    current_status_category = Column(String(255), nullable=True)
    current_status_date = Column(DateTime, nullable=True)

    components = Column(String(1023), nullable=True)  # Comma-separated list of component names
    labels = Column(String(1023), nullable=True)  # Comma-separated list of labels
    resolution = Column(String(255), nullable=True)  # Resolution status, if resolved
    fix_versions = Column('fixVersions', String(1023), nullable=True)
    # Comma-separated fix versions
    attachment_count = Column(Integer, nullable=True)  # Number of attachments

    def __repr__(self):
        """
        Return a string representation of the JiraIssue instance.

        The representation includes the issue's ID, key, summary, 
        and the current status for easy identification.

        Returns:
            str: A string in the format 
                "JiraIssue(id=<id>, key=<key>, summary=<summary>, status=<status>)".
        """
        return (
            f"JiraIssue(id={self.id}, "
            f"key={self.key}, "
            f"summary={self.summary}, "
            f"status={self.status})")
