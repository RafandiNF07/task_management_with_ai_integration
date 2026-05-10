# app/schemas/auth_schema.py
from pydantic import BaseModel
import uuid

# Schema untuk Input (Request)
class UserCreate(BaseModel):
    username: str
    password: str

# Schema untuk Output (Response)
class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    
    class Config:
        from_attributes = True # Memungkinkan Pydantic membaca objek SQLAlchemy/SQLModel

# Schema untuk Token JWT
class TokenResponse(BaseModel):
    access_token: str
    token_type: str