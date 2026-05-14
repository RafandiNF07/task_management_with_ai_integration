import uuid
import enum
from typing import List, Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# --- ENUMS (State Machine & RBAC) ---
class RoleEnum(str, enum.Enum):
    LEADER = "LEADER"
    ASSISTANT = "ASSISTANT"
    QC = "QC"
    MEMBER = "MEMBER"

class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_AI_REVIEW = "PENDING_AI_REVIEW"
    REJECTED_BY_AI = "REJECTED_BY_AI"
    APPEAL_PENDING = "APPEAL_PENDING"
    PENDING_HUMAN_QC = "PENDING_HUMAN_QC"
    REJECTED_BY_HUMAN = "REJECTED_BY_HUMAN"
    DONE = "DONE"

# --- TABLES ---
class Project(SQLModel, table=True):
    __tablename__ = "projects"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=utc_now)
    
    members: List["ProjectMember"] = Relationship(back_populates="project")
    tasks: List["Task"] = Relationship(back_populates="project")

class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_members"  # type: ignore[assignment]
    user_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", primary_key=True)
    role: RoleEnum = Field(default=RoleEnum.MEMBER)
    
    user: "User" = Relationship(back_populates="project_roles")
    project: Project = Relationship(back_populates="members")

class User(SQLModel, table=True):
    __tablename__ = "users"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    
    project_roles: List[ProjectMember] = Relationship(back_populates="user")

class Task(SQLModel, table=True):
    __tablename__ = "tasks"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    raw_content: Optional[str] = Field(default=None)
    deadline: Optional[datetime] = Field(default=None, index=True)
    is_published: bool = Field(default=False, index=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True)
    
    project: Optional[Project] = Relationship(back_populates="tasks")
    subtasks: List["SubTask"] = Relationship(back_populates="task", cascade_delete=True)

class SubTask(SQLModel, table=True):
    __tablename__ = "subtasks"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    description: str
    status: TaskStatus = Field(default=TaskStatus.TODO, index=True)
    
    task_id: uuid.UUID = Field(foreign_key="tasks.id", index=True)
    assigned_to_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    evidence_url: Optional[str] = Field(default=None) 
    
    ai_rejection_reason: Optional[str] = Field(default=None)
    appeal_reason: Optional[str] = Field(default=None)
    human_rejection_reason: Optional[str] = Field(default=None)
    approved_by_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    
    task: Optional[Task] = Relationship(back_populates="subtasks")

class ActivityLog(SQLModel, table=True):
    __tablename__ = "activity_logs"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    action: str 
    details: str
    created_at: datetime = Field(default_factory=utc_now)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    project_id: Optional[uuid.UUID] = Field(default=None, foreign_key="projects.id")


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"  # type: ignore[assignment]
    __table_args__ = ({"extend_existing": True},)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    token: str
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    revoked: bool = Field(default=False, index=True)


