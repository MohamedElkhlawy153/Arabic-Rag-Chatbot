# backend/app/services/knowledge_base_service.py
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.models import UpdateStatus, Record  # Import Record explicitly
from langchain_core.embeddings import Embeddings

from ..schemas import (
    knowledge_base as kb_schemas,
)
from ..core.config import settings

logger = logging.getLogger(__name__)

# Constants remain the same
CHUNK_METADATA_POINT_ID_FIELD = "point_id"
CHUNK_METADATA_SOURCE_FILE_FIELD = "source_file"
CHUNK_METADATA_CHUNK_INDEX_FIELD = "chunk_index"
CHUNK_METADATA_SOURCE_TYPE_FIELD = "source_type"
CHUNK_METADATA_FULL_TEXT_FIELD = "chunk_full_text"
CHUNK_METADATA_UPLOADED_AT_ISO_FIELD = "uploaded_at_iso"
CHUNK_METADATA_TEXT_SNIPPET_FIELD = "text_snippet"
QDRANT_PAYLOAD_METADATA_KEY = "metadata"
LANGCHAIN_CONTENT_KEY = getattr(settings, "LANGCHAIN_CONTENT_KEY", "page_content")


# --- Helper for Schema Conversion ---
# _convert_qdrant_record_to_chunk_detail function remains the same
def _convert_qdrant_record_to_chunk_detail(
    record: Record,  # Use imported Record type hint
) -> kb_schemas.DocumentChunkDetail:
    payload_metadata = (
        record.payload.get(QDRANT_PAYLOAD_METADATA_KEY, {}) if record.payload else {}
    )
    qdrant_point_id_str = str(record.id)

    try:
        chunk_metadata_obj = kb_schemas.DocumentChunkMetadata(
            point_id=qdrant_point_id_str,
            source_file=payload_metadata.get(
                CHUNK_METADATA_SOURCE_FILE_FIELD, "Unknown Source File"
            ),
            chunk_index=payload_metadata.get(CHUNK_METADATA_CHUNK_INDEX_FIELD, -1),
            source_type=payload_metadata.get(
                CHUNK_METADATA_SOURCE_TYPE_FIELD, "document_chunk"
            ),
            uploaded_at_iso=payload_metadata.get(CHUNK_METADATA_UPLOADED_AT_ISO_FIELD),
            text_snippet=payload_metadata.get(CHUNK_METADATA_TEXT_SNIPPET_FIELD),
        )
    except Exception as e:
        logger.error(
            f"Pydantic validation error for DocumentChunkMetadata with point_id {qdrant_point_id_str}, payload metadata: {payload_metadata}. Error: {e}",
            exc_info=True,
        )
        chunk_metadata_obj = kb_schemas.DocumentChunkMetadata(
            point_id=qdrant_point_id_str,
            source_file="Error: Invalid Metadata",
            chunk_index=-2,
            source_type="error",
        )

    full_text_content = payload_metadata.get(CHUNK_METADATA_FULL_TEXT_FIELD, "")
    if not full_text_content:
        if record.payload and record.payload.get(LANGCHAIN_CONTENT_KEY, ""):
            full_text_content = record.payload.get(LANGCHAIN_CONTENT_KEY, "")
            logger.warning(
                f"Chunk with point_id '{qdrant_point_id_str}' using fallback "
                f"'{LANGCHAIN_CONTENT_KEY}' as '{CHUNK_METADATA_FULL_TEXT_FIELD}' was missing/empty in metadata."
            )
        else:
            logger.warning(
                f"Chunk with point_id '{qdrant_point_id_str}' has empty or missing '{CHUNK_METADATA_FULL_TEXT_FIELD}' in metadata "
                f"and no fallback content key '{LANGCHAIN_CONTENT_KEY}' found."
            )

    return kb_schemas.DocumentChunkDetail(
        point_id=qdrant_point_id_str,
        text_content=full_text_content,
        metadata=chunk_metadata_obj,
    )


# --- CRUD Operations for Document Chunks ---


# READ (Get one chunk by its Qdrant point_id)
def get_document_chunk_by_id(
    qdrant_client: QdrantClient,
    point_id: str,
) -> Optional[kb_schemas.DocumentChunkDetail]:
    """Retrieves a specific document chunk from Qdrant by its point_id."""
    logger.info(
        f"Service: Retrieving document chunk from Qdrant by point_id: {point_id}"
    )
    try:
        retrieved_points: List[Record] = (
            qdrant_client.retrieve(  # Use imported Record type hint
                collection_name=settings.QDRANT_COLLECTION_NAME,
                ids=[point_id],
                with_payload=True,
                with_vectors=False,
            )
        )

        if not retrieved_points:
            logger.warning(
                f"Document chunk with point_id '{point_id}' not found in Qdrant retrieve response (list is empty)."
            )
            return None

        point_record = retrieved_points[0]
        return _convert_qdrant_record_to_chunk_detail(point_record)

    except Exception as e:
        logger.error(
            f"Qdrant/Conversion error (get_document_chunk_by_id for '{point_id}'): {e}",
            exc_info=True,
        )
        raise


# READ (List chunks, optionally filtered by source_file)
# list_document_chunks remains correct
def list_document_chunks(
    qdrant_client: QdrantClient,
    source_file: str = None,
    limit: int = 100,
    offset_id: Optional[str] = None,
) -> kb_schemas.DocumentChunkListResponse:
    # This function remains the same as the previous corrected version
    logger.info(
        f"Service: Listing document chunks. Requested source_file filter: '{source_file}', limit: {limit}, offset: {offset_id}"
    )
    filter_conditions = [
        qdrant_models.FieldCondition(
            key=f"{QDRANT_PAYLOAD_METADATA_KEY}.{CHUNK_METADATA_SOURCE_TYPE_FIELD}",
            match=qdrant_models.MatchValue(value="document_chunk"),
        )
    ]
    if source_file:
        filter_conditions.append(
            qdrant_models.FieldCondition(
                key=f"{QDRANT_PAYLOAD_METADATA_KEY}.{CHUNK_METADATA_SOURCE_FILE_FIELD}",
                match=qdrant_models.MatchValue(value=source_file),
            )
        )
    query_filter = qdrant_models.Filter(must=filter_conditions)
    try:
        points_page, next_page_offset_token = qdrant_client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            scroll_filter=query_filter,
            limit=limit,
            offset=offset_id,
            with_payload=True,
            with_vectors=False,
        )
        logger.info(
            f"Qdrant scroll op completed. Points retrieved: {len(points_page)}. First point ID if any: {points_page[0].id if points_page else 'None'}"
        )
        chunks_details = [
            _convert_qdrant_record_to_chunk_detail(point) for point in points_page
        ]
        logger.info(
            f"Converted {len(chunks_details)} points to DocumentChunkDetail schema."
        )
        return kb_schemas.DocumentChunkListResponse(
            chunks=chunks_details,
            next_offset_id=(
                str(next_page_offset_token) if next_page_offset_token else None
            ),
        )
    except Exception as e:
        logger.error(f"Qdrant error (list_document_chunks): {e}", exc_info=True)
        raise


# UPDATE (Modify a chunk's text_content or metadata)
def update_document_chunk(
    qdrant_client: QdrantClient,
    embedding_model: Embeddings,
    point_id: str,
    chunk_update_schema: kb_schemas.DocumentChunkUpdate,
    admin_username: Optional[str] = None,
) -> Optional[kb_schemas.DocumentChunkDetail]:
    logger.info(
        f"Service: Admin '{admin_username}' updating document chunk '{point_id}' in Qdrant."
    )

    try:
        existing_points: List[Record] = (
            qdrant_client.retrieve(  # Use imported Record type hint
                collection_name=settings.QDRANT_COLLECTION_NAME,
                ids=[point_id],
                with_payload=True,
                with_vectors=True,
            )
        )

        if not existing_points:
            logger.warning(
                f"Document chunk with point_id '{point_id}' not found for update (list is empty)."
            )
            return None

        existing_point_record = existing_points[0]

        current_full_payload = (
            existing_point_record.payload if existing_point_record.payload else {}
        )
        current_metadata_payload = current_full_payload.get(
            QDRANT_PAYLOAD_METADATA_KEY, {}
        ).copy()
        current_vector = existing_point_record.vector

        if current_vector is None:
            logger.error(
                f"Point '{point_id}' found but vector is missing (or not retrieved). Cannot update."
            )
            raise ValueError(
                f"Point '{point_id}' is missing its vector, cannot update reliably."
            )

    except Exception as e:
        logger.error(
            f"Qdrant error retrieving point '{point_id}' for update: {e}", exc_info=True
        )
        raise

    # --- Logic for preparing new data ---
    new_vector = current_vector
    text_to_embed_has_changed = False
    new_text_content = current_metadata_payload.get(CHUNK_METADATA_FULL_TEXT_FIELD, "")

    if chunk_update_schema.text_content is not None:
        if chunk_update_schema.text_content != current_metadata_payload.get(
            CHUNK_METADATA_FULL_TEXT_FIELD
        ):
            logger.info(f"Text content changed for chunk '{point_id}'. Re-embedding.")
            new_text_content = chunk_update_schema.text_content
            text_to_embed_has_changed = True

    if text_to_embed_has_changed:
        try:
            new_vector_list = embedding_model.embed_query(new_text_content)
            new_vector = list(map(float, new_vector_list))
            current_metadata_payload[CHUNK_METADATA_FULL_TEXT_FIELD] = new_text_content
            current_metadata_payload[CHUNK_METADATA_TEXT_SNIPPET_FIELD] = (
                new_text_content[:200]
            )
        except Exception as e:
            logger.error(
                f"Embedding update failed for chunk '{point_id}': {e}", exc_info=True
            )
            raise ValueError(f"Embedding update failed: {e}")

    if chunk_update_schema.metadata_updates is not None:
        for key, value in chunk_update_schema.metadata_updates.items():
            if key in [
                CHUNK_METADATA_POINT_ID_FIELD,
                CHUNK_METADATA_SOURCE_TYPE_FIELD,
                CHUNK_METADATA_CHUNK_INDEX_FIELD,
                CHUNK_METADATA_FULL_TEXT_FIELD,
                CHUNK_METADATA_TEXT_SNIPPET_FIELD,
            ]:
                logger.warning(
                    f"Attempt to update restricted/derived metadata field '{key}' for chunk '{point_id}' via 'metadata_updates' was ignored."
                )
                continue
            current_metadata_payload[key] = value

    current_metadata_payload["modified_at_iso"] = datetime.utcnow().isoformat()

    updated_full_payload = current_full_payload.copy()
    updated_full_payload[QDRANT_PAYLOAD_METADATA_KEY] = current_metadata_payload

    if LANGCHAIN_CONTENT_KEY in updated_full_payload or text_to_embed_has_changed:
        updated_full_payload[LANGCHAIN_CONTENT_KEY] = new_text_content

    point_to_update = qdrant_models.PointStruct(
        id=point_id, vector=new_vector, payload=updated_full_payload
    )

    # 3. Upsert the point
    try:
        operation_info = qdrant_client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[point_to_update],
            wait=True,
        )
        if operation_info.status == UpdateStatus.COMPLETED:
            logger.info(f"Successfully updated document chunk '{point_id}' in Qdrant.")
            return get_document_chunk_by_id(qdrant_client, point_id)
        else:
            logger.error(
                f"Qdrant upsert failed for update of chunk '{point_id}', status: {operation_info.status}"
            )
            raise Exception(f"Qdrant upsert for update failed: {operation_info.status}")
    except Exception as e:
        logger.error(
            f"Qdrant error during update_document_chunk ('{point_id}'): {e}",
            exc_info=True,
        )
        raise


# DELETE (a single chunk by its Qdrant point_id)
def delete_document_chunk(
    qdrant_client: QdrantClient,
    point_id: str,
    admin_username: Optional[str] = None,
) -> bool:
    logger.info(
        f"Service: Admin '{admin_username}' deleting document chunk '{point_id}' from Qdrant."
    )
    try:
        existing_points: List[Record] = (
            qdrant_client.retrieve(  # Use imported Record type hint
                collection_name=settings.QDRANT_COLLECTION_NAME,
                ids=[point_id],
                with_payload=False,
                with_vectors=False,
            )
        )

        if not existing_points:
            logger.warning(
                f"Document chunk with point_id '{point_id}' not found. Cannot delete (list is empty)."
            )
            return False

        delete_result = qdrant_client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=qdrant_models.PointIdsList(points=[point_id]),
            wait=True,
        )
        if delete_result.status == UpdateStatus.COMPLETED:
            logger.info(
                f"Successfully deleted document chunk '{point_id}' from Qdrant."
            )
            return True
        else:
            logger.error(
                f"Qdrant delete for '{point_id}' did not complete successfully: {delete_result.status}"
            )
            return False
    except Exception as e:
        logger.error(
            f"Qdrant error during delete_document_chunk ('{point_id}'): {e}",
            exc_info=True,
        )
        return False


# DELETE (all chunks associated with a source_file)
# delete_document_chunks_by_source_file remains correct
def delete_document_chunks_by_source_file(
    qdrant_client: QdrantClient,
    source_file: str,
    admin_username: Optional[str] = None,
) -> dict:
    # This function remains the same as the previous corrected version
    logger.info(
        f"Service: Admin '{admin_username}' deleting ALL document chunks for source_file '{source_file}' from Qdrant."
    )
    query_filter = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key=f"{QDRANT_PAYLOAD_METADATA_KEY}.{CHUNK_METADATA_SOURCE_TYPE_FIELD}",
                match=qdrant_models.MatchValue(value="document_chunk"),
            ),
            qdrant_models.FieldCondition(
                key=f"{QDRANT_PAYLOAD_METADATA_KEY}.{CHUNK_METADATA_SOURCE_FILE_FIELD}",
                match=qdrant_models.MatchValue(value=source_file),
            ),
        ]
    )
    try:
        delete_result = qdrant_client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=qdrant_models.FilterSelector(filter=query_filter),
            wait=True,
        )
        if delete_result.status == UpdateStatus.COMPLETED:
            logger.info(
                f"Successfully sent delete request for all chunks from source_file '{source_file}'. Status: {delete_result.status}"
            )
            return {
                "message": f"Deletion request for chunks from '{source_file}' completed.",
                "status": "success",
            }
        else:
            logger.error(
                f"Qdrant delete by filter for source_file '{source_file}' failed: {delete_result.status}"
            )
            return {
                "message": f"Deletion request for chunks from '{source_file}' failed.",
                "status": "failure",
                "qdrant_status": str(delete_result.status),
            }
    except Exception as e:
        logger.error(
            f"Qdrant error during delete_document_chunks_by_source_file ('{source_file}'): {e}",
            exc_info=True,
        )
        raise


# CREATE (Add a new chunk manually)
def create_manual_document_chunk(
    qdrant_client: QdrantClient,
    embedding_model: Embeddings,
    chunk_create_schema: kb_schemas.DocumentChunkCreateManual,
    admin_username: Optional[str] = None,
) -> kb_schemas.DocumentChunkDetail:
    """Creates a new document chunk manually with the provided text content and source file."""
    logger.info(
        f"Service: Admin '{admin_username}' creating new manual document chunk for source file '{chunk_create_schema.source_file}'"
    )
    
    try:
        # Get existing chunks for this source file to determine next index
        existing_chunks = list_document_chunks(
            qdrant_client=qdrant_client,
            source_file=chunk_create_schema.source_file,
            limit=1000  # Get all chunks to find max index
        )
        
        # Find the next available chunk index
        max_index = -1
        for chunk in existing_chunks.chunks:
            if chunk.metadata.chunk_index > max_index:
                max_index = chunk.metadata.chunk_index
        
        next_index = max_index + 1
        
        # Generate a unique point ID
        point_id = str(uuid.uuid4())
        
        # Create metadata
        metadata = {
            CHUNK_METADATA_POINT_ID_FIELD: point_id,
            CHUNK_METADATA_SOURCE_FILE_FIELD: chunk_create_schema.source_file,
            CHUNK_METADATA_CHUNK_INDEX_FIELD: next_index,  # Use the next available index
            CHUNK_METADATA_SOURCE_TYPE_FIELD: "document_chunk",
            CHUNK_METADATA_FULL_TEXT_FIELD: chunk_create_schema.text_content,
            CHUNK_METADATA_TEXT_SNIPPET_FIELD: chunk_create_schema.text_content[:200],
            CHUNK_METADATA_UPLOADED_AT_ISO_FIELD: datetime.utcnow().isoformat(),
        }
        
        # Create the full payload
        payload = {
            QDRANT_PAYLOAD_METADATA_KEY: metadata,
            LANGCHAIN_CONTENT_KEY: chunk_create_schema.text_content
        }
        
        # Generate embedding for the text content
        try:
            vector = list(map(float, embedding_model.embed_query(chunk_create_schema.text_content)))
        except Exception as e:
            logger.error(f"Embedding generation failed for new chunk: {e}", exc_info=True)
            raise ValueError(f"Failed to generate embedding: {e}")
        
        # Create the point structure
        point = qdrant_models.PointStruct(
            id=point_id,
            vector=vector,
            payload=payload
        )
        
        # Add the point to Qdrant
        operation_info = qdrant_client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[point],
            wait=True
        )
        
        if operation_info.status != UpdateStatus.COMPLETED:
            logger.error(f"Qdrant upsert failed for new chunk, status: {operation_info.status}")
            raise Exception(f"Failed to add chunk to Qdrant: {operation_info.status}")
        
        # Return the created chunk details
        return get_document_chunk_by_id(qdrant_client, point_id)
        
    except Exception as e:
        logger.error(f"Error creating manual document chunk: {e}", exc_info=True)
        raise
