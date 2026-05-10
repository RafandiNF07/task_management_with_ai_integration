# app/schemas/task_schema.py
from pydantic import BaseModel
from typing import List
import uuid

class SubTaskAIResponse(BaseModel):
    title: str
    description: str

class TaskAIResponse(BaseModel):
    task_title: str
    subtasks: List[SubTaskAIResponse]

class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    project_id: uuid.UUID

    class Config:
        from_attributes = True