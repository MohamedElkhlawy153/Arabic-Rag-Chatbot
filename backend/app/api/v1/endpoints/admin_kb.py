# backend/app/api/v1/endpoints/admin_kb.py
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query

from qdrant_client import QdrantClient
from langchain_core.embeddings import Embeddings

from ....api import deps
from ....schemas import knowledge_base as kb_schemas  # Contains DocumentChunk schemas
from ....schemas.common import StandardResponse
from ....services import (
    knowledge_base_service as kb_service,
)  # Contains new service functions
from ....schemas.auth import TokenData

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Dependencies for Qdrant client and Embedding Model ---
def get_qdrant_client_dep() -> QdrantClient:
    return deps.get_qdrant_client()


def get_embedding_model_dep() -> Embeddings:
    return deps.get_embedding_model()


# --- End Dependencies ---


# READ: List document chunks, optionally filtered by source_file
@router.get(
    "/chunks",  # Changed path to reflect "chunks"
    response_model=kb_schemas.DocumentChunkListResponse,
    summary="Admin: List Document Chunks from Global KB",
    description=(
        "Retrieves a list of document chunks from the global knowledge base in Qdrant. "
        "Can be filtered by the original source filename. Supports pagination via Qdrant scroll."
    ),
    dependencies=[Depends(deps.get_current_active_admin)],
)
async def admin_list_document_chunks(
    source_file: str = Query(
        ..., description="Filter chunks by the original source filename."
    ),
    limit: int = Query(
        50, ge=1, le=1000, description="Number of chunks to return per page."
    ),
    offset_id: Optional[str] = Query(
        None,
        description="Qdrant scroll offset ID (from previous response's 'next_offset_id') for pagination.",
    ),
    qdrant_client: QdrantClient = Depends(get_qdrant_client_dep),
):
    try:
        logger.info(
            f"Admin listing document chunks with source_file '{source_file}' and limit {limit}"
        )
        chunk_list_response = kb_service.list_document_chunks(
            qdrant_client=qdrant_client,
            source_file=source_file,
            limit=limit,
            offset_id=offset_id,
        )
        return chunk_list_response
    except Exception as e:
        logger.error(f"Endpoint error (admin_list_document_chunks): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# READ: Get a specific document chunk by its point_id
@router.get(
    "/chunks/{point_id}",  # Path uses point_id
    response_model=kb_schemas.DocumentChunkDetail,
    summary="Admin: Get Specific Document Chunk from Global KB",
    description="Retrieves a specific document chunk by its unique Qdrant point_id. Requires admin authentication.",
    dependencies=[Depends(deps.get_current_active_admin)],
)
async def admin_get_document_chunk(
    point_id: str = Path(
        ..., description="The unique Qdrant point_id of the document chunk."
    ),
    qdrant_client: QdrantClient = Depends(get_qdrant_client_dep),
):
    try:
        chunk = kb_service.get_document_chunk_by_id(
            qdrant_client=qdrant_client, point_id=point_id
        )
        logger.info(
            f"Admin retrieved document chunk with point_id '{point_id}'",
            extra={"chunk": chunk},
        )

        if not chunk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document chunk with point_id '{point_id}' not found.",
            )
        return chunk
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Endpoint error (admin_get_document_chunk) for point_id '{point_id}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# UPDATE: Modify a specific document chunk
@router.put(
    "/chunks/{point_id}",
    response_model=kb_schemas.DocumentChunkDetail,
    summary="Admin: Update Document Chunk in Global KB",
    description=(
        "Updates an existing document chunk in Qdrant using its unique point_id. "
        "If text_content is changed, it will be re-embedded. Requires admin authentication."
    ),
    dependencies=[Depends(deps.get_current_active_admin)],
)
async def admin_update_document_chunk(
    point_id: str = Path(
        ..., description="The unique Qdrant point_id of the chunk to update."
    ),
    chunk_update_schema: kb_schemas.DocumentChunkUpdate = Body(...),
    qdrant_client: QdrantClient = Depends(get_qdrant_client_dep),
    embedding_model: Embeddings = Depends(get_embedding_model_dep),
    current_admin: TokenData = Depends(deps.get_current_active_admin),
):
    try:
        updated_chunk = kb_service.update_document_chunk(
            qdrant_client=qdrant_client,
            embedding_model=embedding_model,
            point_id=point_id,
            chunk_update_schema=chunk_update_schema,
            admin_username=current_admin.username,
        )
        if updated_chunk is None:  # Service returns None if not found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document chunk with point_id '{point_id}' not found for update.",
            )
        return updated_chunk
    except ValueError as ve:  # Catch specific errors like embedding failure
        logger.error(
            f"Validation error during chunk update for point_id '{point_id}': {ve}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve)
        )
    except HTTPException:  # Re-raise 404
        raise
    except Exception as e:
        logger.error(
            f"Endpoint error (admin_update_document_chunk) for point_id '{point_id}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# DELETE: Delete a specific document chunk by its point_id
@router.delete(
    "/chunks/{point_id}",
    response_model=StandardResponse,
    summary="Admin: Delete Document Chunk from Global KB",
    status_code=status.HTTP_200_OK,
    description="Deletes a specific document chunk from Qdrant using its unique point_id. Requires admin authentication.",
    dependencies=[Depends(deps.get_current_active_admin)],
)
async def admin_delete_document_chunk(
    point_id: str = Path(
        ..., description="The unique Qdrant point_id of the document chunk to delete."
    ),
    qdrant_client: QdrantClient = Depends(get_qdrant_client_dep),
    current_admin: TokenData = Depends(deps.get_current_active_admin),
):
    logger.info(
        f"Admin {current_admin.username} attempting to delete document chunk with point_id '{point_id}'"
    )
    try:
        success = kb_service.delete_document_chunk(
            qdrant_client=qdrant_client,
            point_id=point_id,
            admin_username=current_admin.username,
        )
        if not success:  # Service returns False if not found or delete op failed
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document chunk with point_id '{point_id}' not found or delete operation failed.",
            )
        return StandardResponse(
            success=True,
            detail=f"Document chunk with point_id '{point_id}' deleted successfully.",
        )
    except HTTPException:  # Re-raise 404
        raise
    except Exception as e:
        logger.error(
            f"Endpoint error (admin_delete_document_chunk) for point_id '{point_id}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# DELETE: Delete all chunks associated with a source_file
@router.delete(
    "/chunks/by-file/{source_file_name}",  # URL encoding might be needed for source_file_name if it contains special chars
    response_model=StandardResponse,  # Or a more detailed response with count
    summary="Admin: Delete All Chunks for a Source File",
    status_code=status.HTTP_200_OK,
    description=(
        "Deletes all document chunks originating from a specific source_file name "
        "from the global knowledge base in Qdrant. Requires admin authentication."
    ),
    dependencies=[Depends(deps.get_current_active_admin)],
)
async def admin_delete_chunks_by_source_file(
    source_file_name: str = Path(
        ..., description="The name of the source file whose chunks are to be deleted."
    ),
    qdrant_client: QdrantClient = Depends(get_qdrant_client_dep),
    current_admin: TokenData = Depends(deps.get_current_active_admin),
):
    logger.info(
        f"Admin {current_admin.username} attempting to delete all chunks for source_file '{source_file_name}'"
    )
    try:
        # The service function currently returns a dict, adapt response or service.
        # For now, let's assume we just want a StandardResponse.
        result_summary = kb_service.delete_document_chunks_by_source_file(
            qdrant_client=qdrant_client,
            source_file=source_file_name,
            admin_username=current_admin.username,
        )
        if result_summary.get("status") == "failure":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # Or 404 if no chunks found? Service needs to distinguish.
                detail=result_summary.get(
                    "message",
                    f"Failed to delete chunks for source_file '{source_file_name}'.",
                ),
            )
        return StandardResponse(
            success=True,
            detail=result_summary.get(
                "message",
                f"Deletion request for chunks from '{source_file_name}' processed.",
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Endpoint error (admin_delete_chunks_by_source_file) for '{source_file_name}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# CREATE: Add a new document chunk manually
@router.post(
    "/chunks/manual",
    response_model=kb_schemas.DocumentChunkDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: Create New Document Chunk Manually",
    description=(
        "Creates a new document chunk manually with the provided text content and source file. "
        "The text will be embedded using the configured embedding model. Requires admin authentication."
    ),
    dependencies=[Depends(deps.get_current_active_admin)],
)
async def admin_create_manual_document_chunk(
    chunk_create_schema: kb_schemas.DocumentChunkCreateManual = Body(...),
    qdrant_client: QdrantClient = Depends(get_qdrant_client_dep),
    embedding_model: Embeddings = Depends(get_embedding_model_dep),
    current_admin: TokenData = Depends(deps.get_current_active_admin),
):
    logger.info(
        f"Admin {current_admin.username} attempting to create new manual document chunk for source file '{chunk_create_schema.source_file}'"
    )
    try:
        new_chunk = kb_service.create_manual_document_chunk(
            qdrant_client=qdrant_client,
            embedding_model=embedding_model,
            chunk_create_schema=chunk_create_schema,
            admin_username=current_admin.username,
        )
        return new_chunk
    except ValueError as ve:
        logger.error(
            f"Validation error during manual chunk creation: {ve}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(
            f"Endpoint error (admin_create_manual_document_chunk): {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# Note: The POST endpoint for creating individual Q&A pairs is removed from this file
# as the primary way to add knowledge (chunks) is via the /upload endpoint (admin_upload_file_to_global_kb).
# If a separate endpoint for manually adding a single chunk is desired, it would be:
# POST /chunks/manual -> calls a kb_service.create_manual_document_chunk function.
