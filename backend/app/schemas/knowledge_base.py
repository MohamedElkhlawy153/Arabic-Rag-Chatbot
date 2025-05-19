# backend/app/schemas/knowledge_base.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime  # Keep for potential timestamp fields


class DocumentChunkMetadata(BaseModel):
    point_id: (
        str  # This is the Qdrant point ID, it will always exist on a retrieved Record
    )
    source_file: str  # Should ideally always exist from upload
    chunk_index: int  # Should ideally always exist from upload
    source_type: str  # Should ideally always exist from upload
    uploaded_at_iso: Optional[str] = None  # Make it optional if it might be missing
    text_snippet: Optional[str] = None  # Make it optional if it might be missing


class DocumentChunkBase(BaseModel):
    """Base schema for a document chunk's main content."""

    text_content: str = Field(
        ..., description="The full text content of the document chunk."
    )
    metadata: DocumentChunkMetadata = Field(
        description="Metadata associated with the document chunk."
    )


class DocumentChunkCreateManual(BaseModel):
    text_content: str = Field(..., description="The text content of the chunk.")
    source_file: str = Field(
        description="The conceptual source file for this manually added chunk."
    )
    # chunk_index might be tricky for manual adds, maybe it's always 0 or assigned.
    # Or it could be a more general "identifier" within the source_file.
    # metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom metadata for the chunk.")


class DocumentChunkUpdate(BaseModel):
    """Schema for updating a document chunk."""

    text_content: Optional[str] = Field(
        None,
        description="New text content for the chunk. If provided, re-embedding will occur.",
    )
    # Allow updating some metadata fields. Be cautious about which ones.
    # Updating source_file or chunk_index might have implications if they are used for filtering/grouping.
    # It's generally safer to update more superficial metadata or custom tags.
    metadata_updates: Optional[Dict[str, Any]] = Field(
        None,
        description="A dictionary of metadata fields to update. Only provided fields will be changed. "
        "Cannot update 'point_id', 'source_type', 'chunk_index' easily without complex logic.",
    )


class DocumentChunkInQdrant(BaseModel):
    """Representation of a document chunk as retrieved from Qdrant."""

    point_id: str = Field(description="The unique Qdrant point ID for this chunk.")
    text_content: (
        str  # This will be reconstructed or fetched if not directly in payload
    )
    payload: Dict[str, Any] = Field(
        description="The full payload stored in Qdrant for this point."
    )
    score: Optional[float] = Field(
        None, description="Relevance score if retrieved via similarity search."
    )

    # We need a way to get text_content. Qdrant payload for chunks might not store full text
    # if Document.page_content is only used for embedding and not put in payload.
    # Let's assume for admin CRUD, we might need to store/retrieve full text.
    # If LangChain's Qdrant wrapper stores page_content in a specific payload key, we'd use that.
    # For now, this schema assumes text_content might need to be populated.
    #
    # If using LangChain's default, the text is NOT in the payload, it's only in the Document object
    # used for embedding. For admin CRUD, we'd want to store the text IN the payload.
    #
    # Let's adjust upload.py and kb_service to ensure full text is in payload.
    # For now, this schema expects `text_content` to be available.


class DocumentChunkDetail(BaseModel):  # Cleaner representation for GET /chunk/{id}
    point_id: str
    text_content: str
    metadata: DocumentChunkMetadata
    # score: Optional[float] = None # Score usually not relevant for direct GET by ID


class DocumentChunkListResponse(BaseModel):
    chunks: List[DocumentChunkDetail]  # Use the detailed representation for lists
    total_chunks: Optional[int] = Field(
        None, description="Total number of chunks matching the query (if available)."
    )
    next_offset_id: Optional[str] = Field(
        None, description="Offset ID for Qdrant scroll pagination."
    )


# Previous QASchemas are now effectively replaced by DocumentChunk schemas for admin KB purposes.
# If you had a separate feature for admin-curated distinct Q&A pairs (not from documents),
# those schemas (like QAInQdrant from before) would remain, but target a different `source_type`.
# Based on the latest instructions, admin CRUD is on document chunks.
