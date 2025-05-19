# backend/app/schemas/chat.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid


class ChatQueryRequest(BaseModel):
    """Schema for the incoming chat query request."""

    query: str = Field(..., min_length=1)
    # Make session_id required for this RAG approach
    session_id: str = Field(
        ...,
        description="Identifier for the chat session, linked to the uploaded file context.",
    )
    conversation_id: Optional[str] = Field(None)  # Keep if useful
    # metadata_filter is removed, filtering is implicit by session_id
    # use_session_context_only is removed, context is always session-specific


class SourceDocument(BaseModel):
    """Represents a source chunk retrieved for the answer."""

    source_id: str = Field(
        ...,
        description="Identifier for the source chunk (e.g., session:id:filename_chunk_idx).",
    )
    snippet: str = Field(...)
    score: Optional[float] = Field(
        None, description="Relevance score from Qdrant retrieval."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )  # Contains session_id, source_file, etc.


class ChatQueryResponse(BaseModel):
    """Schema for the response sent back."""

    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str = Field(...)
    answer: str = Field(...)
    sources: List[SourceDocument] = Field(...)
    latency_ms: Optional[float] = Field(None)
    conversation_id: Optional[str] = Field(None)
    session_id: Optional[str] = Field(None)  # Echo session ID
