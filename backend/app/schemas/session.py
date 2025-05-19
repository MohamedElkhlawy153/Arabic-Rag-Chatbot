# backend/app/schemas/session.py
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

# Re-using SourceDocument from chat schemas for consistency if needed for sources_data
# from .chat import SourceDocument # If we decide to type sources_data more strictly


class ChatSessionBase(BaseModel):
    session_id: str = Field(description="Unique identifier for the chat session.")
    user_id: Optional[str] = Field(None, description="Identifier for the user, if any.")
    conversation_id: Optional[str] = Field(
        None, description="Optional conversation ID passed in requests."
    )
    metadata_: Optional[Dict[str, Any]] = Field(
        None, description="Arbitrary metadata for the session."
    )


class ChatSessionCreate(ChatSessionBase):
    # Initial data for a new session, typically from the first turn
    queries: List[str] = Field(default_factory=list)
    responses: List[str] = Field(default_factory=list)
    query_ids: List[str] = Field(default_factory=list)  # UUIDs of each turn
    feedback_values: List[Optional[int]] = Field(default_factory=list)  # 1, 0, or None
    sources_data: List[List[Any]] = Field(
        default_factory=list
    )  # List of (List of SourceDocument-like dicts)


class ChatSessionUpdate(BaseModel):
    # Used when appending new turns to an existing session
    queries: Optional[List[str]] = None
    responses: Optional[List[str]] = None
    query_ids: Optional[List[str]] = None
    feedback_values: Optional[List[Optional[int]]] = None
    sources_data: Optional[List[List[Any]]] = (
        None  # List of (List of SourceDocument-like dicts)
    )
    # last_updated_time will be handled by the database


class ChatSessionInDB(ChatSessionBase):
    id: int
    start_time: datetime
    last_updated_time: datetime
    queries: List[str] = Field(default_factory=list)
    responses: List[str] = Field(default_factory=list)
    query_ids: List[str] = Field(default_factory=list)
    feedback_values: List[Optional[int]] = Field(default_factory=list)
    sources_data: List[List[Any]] = Field(
        default_factory=list
    )  # List of (List of SourceDocument-like dicts)

    class Config:
        from_attributes = True  # Pydantic V2 (formerly orm_mode)
