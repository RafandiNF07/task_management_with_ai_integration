# app/schemas/task_schema.py
from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime
import uuid

class SubTaskAIResponse(BaseModel):
    title: str
    description: str

class TaskAIResponse(BaseModel):
    task_title: str
    subtasks: List[SubTaskAIResponse]

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    deadline: datetime | None = None
    project_id: uuid.UUID