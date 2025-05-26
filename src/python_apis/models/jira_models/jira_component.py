from sqlalchemy import Column, String, Integer, Boolean

from python_apis.models.base import Base

class JiraComponent(Base):
    URL_SUFFIX = 'project/UT/components'

    __tablename__ = 'JiraComponent'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1023), nullable=True)
    lead_displayName = Column(String(255), nullable=True)
    lead_accountId = Column(String(255), nullable=True)
    lead_active = Column(Boolean, nullable=True)
    assigneeType = Column(String(255), nullable=True)
    assignee_displayName = Column(String(255), nullable=True)
    assignee_accountId = Column(String(255), nullable=True)
    assignee_active = Column(Boolean, nullable=True)
    realAssigneeType = Column(String(255), nullable=True)
    realAssignee_displayName = Column(String(255), nullable=True)
    realAssignee_accountId = Column(String(255), nullable=True)
    realAssignee_active = Column(Boolean, nullable=True)
    project = Column(String(255), nullable=True)
    projectId = Column(String(255), nullable=True)

    def __repr__(self):
        return (
            f"Component(id={self.id}, name={self.name}, "
            f"lead_displayName={self.lead_displayName}, "
            f"project={self.project}, projectId={self.projectId})"
        )
