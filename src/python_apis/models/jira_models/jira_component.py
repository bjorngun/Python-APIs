"""SQLAlchemy model for representing Jira components."""

from sqlalchemy import Column, String, Integer, Boolean

from python_apis.models.base import Base

class JiraComponent(Base):  # pylint: disable=too-few-public-methods
    """Database model for a Jira component."""
    URL_SUFFIX = 'project/UT/components'

    __tablename__ = 'JiraComponent'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1023), nullable=True)
    lead_display_name = Column('lead_displayName', String(255), nullable=True)
    lead_account_id = Column('lead_accountId', String(255), nullable=True)
    lead_active = Column(Boolean, nullable=True)
    assignee_type = Column('assigneeType', String(255), nullable=True)
    assignee_display_name = Column('assignee_displayName', String(255), nullable=True)
    assignee_account_id = Column('assignee_accountId', String(255), nullable=True)
    assignee_active = Column(Boolean, nullable=True)
    real_assignee_type = Column('realAssigneeType', String(255), nullable=True)
    real_assignee_display_name = Column('realAssignee_displayName', String(255), nullable=True)
    real_assignee_account_id = Column('realAssignee_accountId', String(255), nullable=True)
    real_assignee_active = Column(Boolean, nullable=True)
    project = Column(String(255), nullable=True)
    project_id = Column('projectId', String(255), nullable=True)

    def __repr__(self):
        return (
            f"Component(id={self.id}, name={self.name}, "
            f"lead_display_name={self.lead_display_name}, "
            f"project={self.project}, project_id={self.project_id})"
        )
