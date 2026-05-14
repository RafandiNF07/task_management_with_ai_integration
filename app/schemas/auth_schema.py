# app/schemas/auth_schema.py
from pydantic import BaseModel, ConfigDict
import uuid

# Schema untuk Input (Request)
class UserCreate(BaseModel):
    username: str
    password: str

# Schema untuk Output (Response)
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str


# Schema untuk Token JWT
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    # Optional refresh token (jika ada)
    refresh_token: str | None = None


# Request payload untuk refresh token
class RefreshRequest(BaseModel):
    refresh_token: str
    refresh_token: str | None = None