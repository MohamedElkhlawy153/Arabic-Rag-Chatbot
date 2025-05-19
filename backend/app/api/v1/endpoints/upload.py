# backend/app/api/v1/endpoints/upload.py

import time
import logging
import uuid
import os
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
)  # Removed Form
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# LangChain imports
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_qdrant import Qdrant

import cohere

# from ....schemas.common import StandardResponse # Not used directly in this endpoint's response
from ....api import deps
from ....utils import text_processing
from ....core.config import settings
from ....services.log_service import log_generic_event_to_db
from ....db import models  # For IngestedDocument logging
from ....schemas.upload import UploadResponse  # Response schema

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
UPSERT_BATCH_SIZE = settings.COHERE_EMBED_BATCH_SIZE


                 

@router.post(
    "/",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: Upload File to Global Knowledge Base",
    description=(
        "Admin uploads a file (PDF, TXT, CSV). The file is processed into chunks, embedded using Cohere, "
        "and stored in Qdrant as part of the global, shared knowledge base. "
        "These chunks are NOT session-specific."
    ),
    dependencies=[Depends(deps.get_current_active_admin)],
)
async def admin_upload_file_to_global_kb(
    file: UploadFile = File(...),
    vector_store: Qdrant = Depends(deps.get_langchain_qdrant),
    db: Session = Depends(deps.get_db_session),
):
    """
    Handles admin file upload to populate the global knowledge base in Qdrant.
    Chunks are not tied to a user session.
    """
    upload_instance_id = str(uuid.uuid4())
    logger.info(f"Admin performing global KB upload. Instance ID: {upload_instance_id}. Filename: '{file.filename}'.")
    ingestion_status = "Failed"
    error_message = None
    chunk_count = 0
    qdrant_point_ids_added = []  
    start_time = time.time()

    try:
        # --- 1. File Validation ---
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large",
            )
        
        file_extension = os.path.splitext(file.filename)[1].lower()
        supported_extensions = [".pdf", ".txt", ".csv"]
        if file_extension not in supported_extensions:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: {file_extension}"
            )

        # --- 2. Text Extraction & Processing ---
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File content is empty.")

        extracted_text = ""
        text_chunks = []

        if file_extension == ".pdf":
            extracted_text = text_processing.load_pdf(file_content)
            text_chunks = text_processing.chunk_text(
                text=extracted_text,
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )
        
        elif file_extension == ".txt":
            extracted_text = file_content.decode("utf-8")
            text_chunks = text_processing.chunk_text(
                text=extracted_text,
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )

        elif file_extension == ".csv":
            import pandas as pd
            from io import BytesIO

            csv_data = pd.read_csv(BytesIO(file_content))
             # Automatically rename columns if not exactly "query" and "response"
            column_names = [col.lower().strip() for col in csv_data.columns]
            if "query" not in column_names or "response" not in column_names:
                             # Attempt to auto-detect and rename columns
                    if len(column_names) >= 2:
                               csv_data.columns = ["query", "response"] + column_names[2:]
                               logger.warning(
                                   f"CSV columns automatically renamed to 'query' and 'response'."
                                            )
            else:
                     raise HTTPException(
                              status_code=status.HTTP_400_BAD_REQUEST,
                                detail="CSV file must contain at least two columns for 'query' and 'response'."
                                        )
            

            for index, row in csv_data.iterrows():
                query_text = str(row["query"]).strip()
                response_text = str(row["response"]).strip()
                if query_text:
                    text_chunks.append(f"سؤال: {query_text}\nإجابة: {response_text}")

        if not text_chunks:
            return UploadResponse(
                success=True,
                detail=f"File '{file.filename}' processed for global KB, but no text content found to add.",
                session_id=upload_instance_id,
                filename=file.filename,
                chunks_added=0,
            )

        # --- 3. Prepare LangChain Documents & Qdrant Point IDs ---
        documents_to_add = []
        ids_for_qdrant = []

        for i, chunk_text in enumerate(text_chunks):
            point_uuid = str(uuid.uuid4())
            ids_for_qdrant.append(point_uuid)
            qdrant_point_ids_added.append(point_uuid)

            metadata = {
                "source_file": file.filename,
                "chunk_index": i,
                "text_snippet": chunk_text[:200], 
                "point_id": point_uuid,
                "source_type": "document_chunk",
                "uploaded_at_iso": datetime.utcnow().isoformat(),
            }

            documents_to_add.append(
                Document(page_content=chunk_text, metadata=metadata)
            )

        # --- 4. Add New Documents to Qdrant ---
        vector_store.add_documents(
            documents=documents_to_add,
            ids=ids_for_qdrant,
            batch_size=UPSERT_BATCH_SIZE,
        )

        ingestion_status = "Success"

        return UploadResponse(
            session_id=upload_instance_id,
            detail=f"File '{file.filename}' successfully ingested into the global knowledge base. Chunks added: {len(documents_to_add)}.",
            success=True,
            filename=file.filename,
            chunks_added=len(documents_to_add),
        )

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(
            f"Global KB upload pre-processing error ({upload_instance_id}), file '{file.filename}': {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


    finally:
        if file:
            await file.close()

        latency_ms_calc = (time.time() - start_time) * 1000
        if db:  # Log to SQL database (IngestedDocument and GenericEventLog)
            try:
                # Log to IngestedDocument: This table tracks admin uploads to global KB
                # Its 'session_id' column now effectively means 'upload_batch_id' or similar unique upload op ID.
                # Or, we could rename the column in IngestedDocument model if this is confusing.
                # For now, let's use upload_instance_id for the IngestedDocument's session_id field.
                db_ingested_doc_log = models.IngestedDocument(
                    session_id=upload_instance_id,  # Using upload_instance_id for this log's grouping
                    source_identifier=file.filename if file else "N/A",
                    status=ingestion_status,
                    chunk_count=chunk_count if ingestion_status == "Success" else 0,
                    error_message=(
                        error_message if ingestion_status == "Failed" else None
                    ),
                )
                db.add(db_ingested_doc_log)

                log_generic_event_to_db(
                    db=db,
                    event_type="ADMIN_GLOBAL_KB_INGESTION",
                    status=ingestion_status.upper(),
                    details=(
                        f"Admin KB Upload. File: {file.filename if file else 'N/A'}. "
                        f"Instance: {upload_instance_id}. "
                        f"Chunks processed: {chunk_count}. "
                        f"Qdrant Points Added: {len(qdrant_point_ids_added) if ingestion_status == 'Success' else 0}. "
                        f"{('Error: ' + error_message) if error_message and ingestion_status == 'Failed' else ''}"
                    ).strip(),
                    component_id=upload_instance_id,  # This specific upload operation
                    related_id=file.filename if file else None,
                    latency_ms=latency_ms_calc,
                    extra_data={
                        "file_size": file.size if file else None,
                        "file_type": (
                            os.path.splitext(file.filename)[1].lower()
                            if file and file.filename
                            else None
                        ),
                        "qdrant_point_ids": (
                            qdrant_point_ids_added
                            if ingestion_status == "Success"
                            else []
                        ),
                    },
                )
                db.commit()
                logger.info(
                    f"Admin global KB ingestion attempt for file '{file.filename if file else 'N/A'}' (Instance {upload_instance_id}) logged to DB."
                )
            except SQLAlchemyError as db_err:
                logger.error(
                    f"Failed to log admin global KB ingestion (Instance {upload_instance_id}) to DB: {db_err}",
                    exc_info=True,
                )
                if db:
                    db.rollback()
            except Exception as log_err:
                logger.error(
                    f"Unexpected error during DB logging for admin global KB ingestion (Instance {upload_instance_id}): {log_err}",
                    exc_info=True,
                )
                if db:
                    db.rollback()
