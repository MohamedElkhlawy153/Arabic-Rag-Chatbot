from pydantic import BaseModel, Field
from typing import Optional, Literal


class FeedbackRequest(BaseModel):
    """Schema for the feedback submitted by an agent regarding a chat response."""

    session_id: str = Field(
        ...,
        description="The unique identifier of the chat session this feedback refers to.",
    )

    query_id: str = Field(
        ...,
        description="The unique identifier of the query/response this feedback refers to (from ChatQueryResponse).",
    )
    rating: Literal[0, 1] = Field(
        ..., description="1 for positive feedback, 0 for negative feedback."
    )
    comment: Optional[str] = Field(
        None, max_length=1000, description="Optional textual comment from the agent."
    )
    # Include snapshots if needed for analysis when feedback is separate from logs
    query_text_snapshot: Optional[str] = Field(
        None, description="Snapshot of the query text for context."
    )
    response_text_snapshot: Optional[str] = Field(
        None, description="Snapshot of the response text for context."
    )
