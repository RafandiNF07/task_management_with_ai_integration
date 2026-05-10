# app/schemas/project_schema.py
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
import uuid
from app.models.domain import RoleEnum

class ProjectCreate(BaseModel):
    name: str

class MemberInvite(BaseModel):
    username: str
    role: RoleEnum = RoleEnum.MEMBER

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str

class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    role: RoleEnum