# app/schemas/project_schema.py
from pydantic import BaseModel
from typing import List, Optional
import uuid
from app.models.domain import RoleEnum

class ProjectCreate(BaseModel):
    name: str

class MemberInvite(BaseModel):
    username: str
    role: RoleEnum = RoleEnum.MEMBER

class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    
    class Config:
        from_attributes = True

class ProjectMemberResponse(BaseModel):
    username: str
    role: RoleEnum

    class Config:
        from_attributes = True