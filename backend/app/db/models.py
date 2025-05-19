# backend/app/db/models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Float,
    # Boolean, # No longer needed from Feedback
    # ForeignKey, # No longer needed
    JSON,  # For storing lists/structured data
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.schema import Index

Base = declarative_base()
"""Base class for SQLAlchemy declarative models."""


class ChatSession(Base):
    """SQLAlchemy model for storing an entire chat session in a single row."""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=True)  # Optional user identifier

    start_time = Column(DateTime(timezone=True), server_default=func.now())
    last_updated_time = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Storing conversation history as JSON arrays
    # For SQLite, SQLAlchemy's JSON type often maps to TEXT.
    # For PostgreSQL, it can map to JSON or JSONB.
    queries = Column(JSON, default=lambda: [])  # List of user queries (strings)
    responses = Column(JSON, default=lambda: [])  # List of bot responses (strings)
    query_ids = Column(
        JSON, default=lambda: []
    )  # List of unique ID for each query-response turn (strings/UUIDs)
    feedback_values = Column(
        JSON, default=lambda: []
    )  # List of feedback (0, 1, or null)
    sources_data = Column(
        JSON, default=lambda: []
    )  # List of lists of source documents for each response

    conversation_id = Column(
        String(255), nullable=True
    )  # Optional, from original request
    metadata_ = Column(
        JSON, nullable=True
    )  # Using metadata_ to avoid conflict with SQLAlchemy's 'metadata'

    __table_args__ = (
        Index("ix_chat_sessions_user_id_last_updated", "user_id", "last_updated_time"),
    )

    def __repr__(self):
        return f"<ChatSession(id={self.id}, session_id='{self.session_id}', user_id='{self.user_id}', turns='{len(self.queries) if self.queries else 0}')>"


class QuestionAnswerPair(Base):
    """
    Represents admin-curated Q&A pairs, potentially linked to a session_id
    where they might have originated or are relevant.
    This table is NOT for logging live chat conversations.
    """

    __tablename__ = "question_answer_pairs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(
        String(255), index=True, nullable=False
    )  # Can link to a ChatSession or be generic
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<QuestionAnswerPair(id={self.id}, session_id='{self.session_id}', question='{self.question[:30]}...')>"


class IngestedDocument(Base):
    """Tracks documents ingested into the vector store, associated with a session."""

    __tablename__ = "ingested_documents"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    source_identifier = Column(String, index=True, nullable=False)
    last_ingested_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    status = Column(String(20), default="Success", index=True)
    chunk_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_ingested_documents_session_id_source", "session_id", "source_identifier"
        ),
    )


class GenericEventLog(Base):
    """SQLAlchemy model for storing generic application system events."""

    __tablename__ = "generic_event_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    event_type = Column(
        String(100), index=True, nullable=False
    )  # e.g., "INGESTION_ATTEMPT", "SYSTEM_STARTUP"
    status = Column(
        String(20), index=True, nullable=True
    )  # e.g., "SUCCESS", "FAILURE", "INFO"
    details = Column(Text, nullable=True)  # General details about the event
    component_id = Column(
        String(255), nullable=True
    )  # e.g., session_id, user_id, filename
    related_id = Column(String(255), nullable=True)  # Any other relevant ID
    latency_ms = Column(
        Float, nullable=True
    )  # For performance tracking of the event itself
    extra_data = Column(JSON, nullable=True)  # For any additional structured data

    __table_args__ = (
        Index("ix_generic_event_logs_type_time", "event_type", "timestamp"),
    )

    def __repr__(self):
        return f"<GenericEventLog(id={self.id}, event_type='{self.event_type}', status='{self.status}')>"
