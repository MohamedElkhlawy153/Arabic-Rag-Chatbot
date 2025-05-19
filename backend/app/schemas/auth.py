# backend/app/schemas/auth.py
from pydantic import BaseModel, Field
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")


class TokenData(BaseModel):
    username: Optional[str] = None
    # Add other claims if needed, e.g., roles, user_id


class UserLoginRequest(BaseModel):  # Renamed for clarity
    username: str
    password: str


# For the response from /login
class UserAuthDetails(BaseModel):  # User details to return on login
    username: str
    # email: Optional[str] = None # Add other fields as necessary
    # full_name: Optional[str] = None


class LoginResponse(BaseModel):
    token: Token
    user: UserAuthDetails
