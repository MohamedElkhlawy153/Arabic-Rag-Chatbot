# backend/app/schemas/upload.py

from pydantic import Field
from .common import StandardResponse  # Import the base response


class UploadResponse(StandardResponse):
    """
    Response schema for the file upload and ingestion endpoint.
    Extends the standard response with upload-specific details.
    """

    session_id: str = Field(
        ..., description="The unique session ID assigned to this upload context."
    )
    filename: str = Field(..., description="The name of the file that was uploaded.")
    chunks_added: int = Field(
        ...,
        description="The number of text chunks successfully processed and added to the vector store.",
    )
