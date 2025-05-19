# backend/app/services/chat_service.py

import logging
import time
import uuid
from typing import Optional, List, Tuple  # Tuple is not used, can be removed

# Cohere Imports
import cohere
from ..utils.cohere_utils import get_cohere_client

# Google Gemini Imports
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from ..utils.gemini_utils import get_gemini_model

# LangChain Imports
from langchain_qdrant import Qdrant
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

# Qdrant Imports
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

# SQLAlchemy Imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Local Imports
from ..core.config import settings
from ..schemas.chat import ChatQueryRequest, ChatQueryResponse, SourceDocument
from ..schemas import session as session_schemas
from ..db import models
from ..api.deps import get_langchain_qdrant  # For embedding model via Langchain Qdrant


METADATA_KEY_SOURCE_FILE = "source_file"
METADATA_KEY_CHUNK_INDEX = "chunk_index"
METADATA_KEY_POINT_ID = "point_id"  # This is the Qdrant ID for the chunk
METADATA_KEY_SOURCE_TYPE = "source_type"

logger = logging.getLogger(__name__)

# --- RAG Prompt Structure ---
RAG_SYSTEM_PROMPT = " ".join(
    [
        "أنت مساعد الذكاء الاصطناعي. أجب على السؤال التالي بناءً على السياق المقدم فقط.",
        "كن دقيقاً وموجزاً. إذا كانت المعلومات غير موجودة في السياق، قل بوضوح 'المعلومات غير متوفرة في المستند المقدم'.",  # Corrected typo
        "لا تختلق إجابات خارج السياق المقدم. استخدم اللغة العربية فقط للإجابة.",
    ]
)
RAG_USER_PROMPT_TEMPLATE = """السياق:
{context}

السؤال: {question}"""


# --- Helper Functions for SQL ChatSession Management ---
def _get_or_create_session(
    db: Session,
    session_id: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> models.ChatSession:
    """
    Retrieves an existing ChatSession from SQL DB or creates a new one.
    Commits the new session immediately.
    """
    chat_session_sql = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.session_id == session_id)
        .first()
    )
    if not chat_session_sql:
        logger.info(f"Creating new SQL ChatSession in DB for session_id: {session_id}")
        new_session_schema = session_schemas.ChatSessionCreate(
            session_id=session_id,
            user_id=user_id,
            conversation_id=conversation_id,
            # Initialize empty lists
            queries=[],
            responses=[],
            query_ids=[],
            feedback_values=[],
            sources_data=[],
        )
        chat_session_sql = models.ChatSession(**new_session_schema.model_dump())
        try:
            db.add(chat_session_sql)
            db.commit()
            db.refresh(chat_session_sql)
            logger.info(
                f"New SQL ChatSession created with DB ID: {chat_session_sql.id} for session_id: {session_id}"
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(
                f"Failed to create new SQL ChatSession for session_id {session_id}: {e}",
                exc_info=True,
            )
            # This is a critical failure if we can't even create the session log
            raise Exception(
                f"Could not initialize chat session log: {e}"
            ) from e  # Changed to generic Exception
    else:
        logger.info(
            f"Found existing SQL ChatSession in DB for session_id: {session_id}, DB ID: {chat_session_sql.id}"
        )
    return chat_session_sql


def _update_session_in_db(
    db: Session,
    chat_session_sql: models.ChatSession,  # The SQL ChatSession object
    query_text: str,
    response_text: str,
    turn_query_id: str,  # Renamed from query_id for clarity
    sources: List[SourceDocument],
    conversation_id: Optional[str],
) -> bool:
    """
    Appends the current turn's data to the SQL ChatSession object and commits to DB.
    """
    try:
        chat_session_sql.queries = (chat_session_sql.queries or []) + [query_text]
        chat_session_sql.responses = (chat_session_sql.responses or []) + [
            response_text
        ]
        chat_session_sql.query_ids = (chat_session_sql.query_ids or []) + [
            turn_query_id
        ]
        chat_session_sql.feedback_values = (chat_session_sql.feedback_values or []) + [
            None
        ]

        sources_for_json = [s.model_dump() for s in sources]  # Pydantic models to dicts
        chat_session_sql.sources_data = (chat_session_sql.sources_data or []) + [
            sources_for_json
        ]

        if conversation_id and not chat_session_sql.conversation_id:
            chat_session_sql.conversation_id = conversation_id

        db.add(chat_session_sql)
        db.commit()
        # db.refresh(chat_session_sql) # Refresh if you need updated fields like last_updated_time immediately
        logger.info(
            f"SQL ChatSession {chat_session_sql.session_id} (DB ID: {chat_session_sql.id}) updated with new turn. "
            f"Total turns: {len(chat_session_sql.queries)}"
        )
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Failed to update SQL ChatSession {chat_session_sql.session_id} in database: {e}",
            exc_info=True,
        )
        return False
    except Exception as e:
        db.rollback()
        logger.error(
            f"Unexpected error updating SQL ChatSession {chat_session_sql.session_id}: {e}",
            exc_info=True,
        )
        return False


# --- Main Service Function ---
async def process_agent_query(
    request: ChatQueryRequest, db: Session  # db is for SQL ChatSession
) -> ChatQueryResponse:
    """
    Processes a user query:
    1. Retrieves relevant context from the GLOBAL Qdrant knowledge base (document chunks).
    2. Generates an answer using an LLM (Gemini) with the retrieved context.
    3. Logs the entire conversation turn (query, answer, sources, feedback placeholder)
       to the user's specific session row in the SQL `ChatSession` table.
    """
    start_time = time.perf_counter()
    query = request.query
    user_chat_session_id = (
        request.session_id
    )  # ID for the SQL ChatSession (conversation log)
    turn_query_id = str(uuid.uuid4())  # Unique ID for this specific query-response turn

    # Default error response values
    answer = "عذراً، حدث خطأ أثناء محاولة إنشاء الإجابة."
    formatted_sources: List[SourceDocument] = []
    initial_retrieved_docs: List[Document] = []  # Docs from Qdrant
    reranked_docs: List[Document] = []
    latency_ms = None
    generation_llm_used = "Gemini"

    # Get or Create the SQL ChatSession for logging this conversation
    current_sql_chat_session = _get_or_create_session(
        db, user_chat_session_id, user_id=None, conversation_id=request.conversation_id
    )

    logger.info(
        f"Processing query for SQL ChatSession: {user_chat_session_id} (DB ID: {current_sql_chat_session.id}), "
        f"Turn ID: {turn_query_id}. Query: '{query[:100]}...'"
    )

    try:
        # --- Get Qdrant and Cohere Components ---
        vector_store: Qdrant = get_langchain_qdrant()  # LangChain Qdrant wrapper
        cohere_client: cohere.Client = get_cohere_client()

        # --- 1. Initial Retrieval from GLOBAL KNOWLEDGE BASE (Qdrant) ---
        logger.debug(
            f"Step 1: Initial retrieval for turn {turn_query_id} from Global KB (Qdrant)"
        )
        retrieval_start_time = time.perf_counter()
        context_string = "لا يوجد سياق متاح من المستندات المرجعية."  # Default

        try:
            # Filter for global document chunks in Qdrant
            qdrant_filter_for_global_kb = Filter(
                must=[
                    FieldCondition(
                        key="metadata.source_type",
                        match=MatchValue(value="document_chunk"),
                    )
                ]
            )
            global_kb_retriever: BaseRetriever = vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={
                    "k": settings.RETRIEVER_K,
                    "filter": qdrant_filter_for_global_kb,
                },
            )
            initial_retrieved_docs = global_kb_retriever.invoke(query)
            retrieval_latency = (time.perf_counter() - retrieval_start_time) * 1000
            logger.info(
                f"Step 1 (Turn {turn_query_id}): Global KB retrieval found {len(initial_retrieved_docs)} docs. "
                f"Latency: {retrieval_latency:.2f}ms"
            )
        except cohere.ApiException as co_err:
            logger.error(
                f"Cohere API error during query embedding for retrieval (Turn {turn_query_id}): {co_err}"
            )
        except Exception as e:
            logger.error(
                f"Error during Qdrant retrieval from Global KB (Turn {turn_query_id}): {e}",
                exc_info=True,
            )

        # --- 2. Reranking with Cohere ---
        logger.debug(f"Step 2: Reranking docs for turn {turn_query_id}")
        if initial_retrieved_docs:
            rerank_start_time = time.perf_counter()
            try:
                docs_to_rerank_content = [
                    doc.page_content for doc in initial_retrieved_docs
                ]
                rerank_api_response = cohere_client.rerank(
                    query=query,
                    documents=docs_to_rerank_content,
                    top_n=settings.RERANK_TOP_N,
                    model=settings.COHERE_RERANK_MODEL,
                )

                temp_reranked_results = []
                for r_result in rerank_api_response.results:  # cohere.RerankResult
                    original_doc = initial_retrieved_docs[r_result.index]
                    if original_doc.metadata is None:
                        original_doc.metadata = {}
                    original_doc.metadata["rerank_score"] = r_result.relevance_score
                    original_doc.metadata["original_retrieval_rank"] = r_result.index
                    temp_reranked_results.append(original_doc)
                reranked_docs = temp_reranked_results

                rerank_latency = (time.perf_counter() - rerank_start_time) * 1000
                logger.info(
                    f"Step 2 (Turn {turn_query_id}): Reranked {len(initial_retrieved_docs)} -> {len(reranked_docs)} docs. "
                    f"Latency: {rerank_latency:.2f}ms"
                )
                if reranked_docs:
                    context_string = "\n\n---\n\n".join(
                        [doc.page_content for doc in reranked_docs]
                    )
                else:
                    context_string = "لا يوجد سياق متاح بعد إعادة الترتيب."
            except cohere.ApiException as co_err:
                logger.error(
                    f"Cohere API error during reranking (Turn {turn_query_id}): {co_err}"
                )
                reranked_docs = initial_retrieved_docs  # Fallback
                if reranked_docs:
                    context_string = "\n\n---\n\n".join(
                        [doc.page_content for doc in reranked_docs]
                    )
                logger.warning(
                    f"Falling back to {len(reranked_docs)} initial docs due to rerank error (Turn {turn_query_id})."
                )
            except Exception as e:
                logger.error(
                    f"Error during reranking (Turn {turn_query_id}): {e}", exc_info=True
                )
                reranked_docs = initial_retrieved_docs  # Fallback
                if reranked_docs:
                    context_string = "\n\n---\n\n".join(
                        [doc.page_content for doc in reranked_docs]
                    )
                logger.warning(
                    f"Falling back to {len(reranked_docs)} initial docs due to rerank error (Turn {turn_query_id})."
                )
        else:
            logger.info(
                f"Step 2 (Turn {turn_query_id}): Skipped reranking (no initial documents)."
            )
            # context_string remains "لا يوجد سياق متاح من المستندات المرجعية."

        # --- 3. Generation with Gemini ---
        logger.debug(
            f"Step 3: Generating response with {generation_llm_used} for turn {turn_query_id}"
        )
        generation_start_time = time.perf_counter()
        generated_answer_text = None  # Store the actual text from LLM
        try:
            gemini_model_instance = get_gemini_model(
                system_instruction=RAG_SYSTEM_PROMPT
            )
            user_prompt_for_llm = RAG_USER_PROMPT_TEMPLATE.format(
                context=context_string, question=query
            )

            gemini_gen_config = genai.types.GenerationConfig(
                max_output_tokens=settings.GENERATION_MAX_OUTPUT_TOKENS,
                temperature=settings.GENERATION_TEMPERATURE,
                top_p=settings.GENERATION_TOP_P,
            )
            if settings.GENERATION_TOP_K is not None:
                gemini_gen_config.top_k = settings.GENERATION_TOP_K

            safety_settings_gemini = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            gemini_api_response = await gemini_model_instance.generate_content_async(
                contents=[user_prompt_for_llm],
                generation_config=gemini_gen_config,
                safety_settings=safety_settings_gemini,
            )

            if (
                gemini_api_response.candidates
                and not gemini_api_response.prompt_feedback.block_reason
            ):
                generated_answer_text = gemini_api_response.text
            elif gemini_api_response.prompt_feedback.block_reason:
                block_reason_str = (
                    gemini_api_response.prompt_feedback.block_reason.name
                )  # Get enum name
                logger.error(
                    f"Gemini generation blocked for turn {turn_query_id}. Reason: {block_reason_str}"
                )
                answer = f"عذراً، لا يمكنني إنشاء رد بسبب قيود السلامة ({block_reason_str})."  # Update the main 'answer'
            else:
                logger.error(
                    f"Gemini generation yielded no candidates for turn {turn_query_id}. Response: {gemini_api_response}"
                )
                # 'answer' remains the default error message

            generation_latency = (time.perf_counter() - generation_start_time) * 1000
            if generated_answer_text is not None:
                logger.info(
                    f"Step 3 (Turn {turn_query_id}): {generation_llm_used} generation complete. Latency: {generation_latency:.2f}ms"
                )
                answer = generated_answer_text  # Update main 'answer' with successful generation
            else:  # If generated_answer_text is still None (and not blocked with specific message)
                logger.error(
                    f"Step 3 (Turn {turn_query_id}): {generation_llm_used} generation failed or was empty. Latency: {generation_latency:.2f}ms"
                )
                # 'answer' remains the default error message or safety block message

        except google_exceptions.GoogleAPIError as e:
            logger.error(
                f"Google API error during {generation_llm_used} generation (Turn {turn_query_id}): {e}",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during {generation_llm_used} generation (Turn {turn_query_id}): {e}",
                exc_info=True,
            )

        # --- Format Sources for Response ---
        docs_considered_for_sources = reranked_docs if reranked_docs else []
        for i, doc_source in enumerate(docs_considered_for_sources):
            metadata_from_qdrant = doc_source.metadata if doc_source.metadata else {}

            source_file_name = metadata_from_qdrant.get(
                METADATA_KEY_SOURCE_FILE, "Unknown File"
            )
            chunk_idx_val = metadata_from_qdrant.get(METADATA_KEY_CHUNK_INDEX, i)
            # The point_id in metadata should be the Qdrant ID of the chunk itself
            qdrant_point_id_val = metadata_from_qdrant.get(
                METADATA_KEY_POINT_ID,
                f"unknown_point_{doc_source.id if hasattr(doc_source, 'id') else i}",
            )  # Fallback for safety

            client_visible_source_id = (
                f"session:{user_chat_session_id}:file:{source_file_name}"
                f"_chunkidx:{chunk_idx_val}_pointid:{qdrant_point_id_val}"
            )

            relevance_score = metadata_from_qdrant.get(
                "rerank_score",
                metadata_from_qdrant.get("_score", metadata_from_qdrant.get("score")),
            )

            formatted_sources.append(
                SourceDocument(
                    source_id=client_visible_source_id,
                    snippet=doc_source.page_content,
                    score=relevance_score,
                    metadata=metadata_from_qdrant,
                )
            )

        end_time = time.perf_counter()
        latency_ms = round((end_time - start_time) * 1000, 2)

        # --- Update SQL ChatSession in DB with the new turn ---
        db_update_successful = _update_session_in_db(
            db=db,
            chat_session_sql=current_sql_chat_session,
            query_text=query,
            response_text=answer,  # This is the final answer (generated or error)
            turn_query_id=turn_query_id,
            sources=formatted_sources,
            conversation_id=request.conversation_id,
        )
        if db_update_successful:
            logger.info(
                f"Successfully processed and logged turn {turn_query_id} for SQL ChatSession {user_chat_session_id}."
            )
        else:
            logger.error(
                f"CRITICAL: Failed to log turn {turn_query_id} to SQL ChatSession {user_chat_session_id}."
            )
            # The chat response will still be sent to the user, but the turn isn't saved in DB.

        logger.info(
            f"Response for turn {turn_query_id}: '{answer[:100]}...'. Latency: {latency_ms}ms. Sources: {len(formatted_sources)}"
        )

        return ChatQueryResponse(
            query_id=turn_query_id,
            query=query,
            answer=answer,  # Final answer
            sources=formatted_sources,
            latency_ms=latency_ms,
            conversation_id=request.conversation_id,
            session_id=user_chat_session_id,  # Echo back the user's SQL chat session ID
        )

    except RuntimeError as e:  # E.g., Cohere client init error, Qdrant client init
        logger.critical(
            f"Critical runtime error during query processing for SQL ChatSession {user_chat_session_id}, turn {turn_query_id}: {e}",
            exc_info=True,
        )
        # Don't attempt to log to SQL ChatSession here as the error might be with DB itself or core components
        raise  # Re-raise to be handled by FastAPI global error handlers
    except Exception as e:  # Catch-all for unexpected errors during the main try block
        logger.error(
            f"Unhandled exception during query processing for SQL ChatSession {user_chat_session_id}, turn {turn_query_id}: {e}",
            exc_info=True,
        )
        if latency_ms is None:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Attempt to log this failed turn to the SQL ChatSession
        _update_session_in_db(
            db=db,
            chat_session_sql=current_sql_chat_session,
            query_text=query,
            response_text=answer,  # Default error answer
            turn_query_id=turn_query_id,
            sources=[],
            conversation_id=request.conversation_id,
        )
        # Return the default error response to the client
        return ChatQueryResponse(
            query_id=turn_query_id,
            query=query,
            answer=answer,
            sources=[],
            latency_ms=latency_ms,
            conversation_id=request.conversation_id,
            session_id=user_chat_session_id,
        )
