# backend/app/api/v1/endpoints/chat.py

import logging
from fastapi import APIRouter, Depends, HTTPException, Body, status  # Import status
from sqlalchemy.orm import Session

from ....schemas import chat as chat_schemas
from ....services import chat_service
from ....api import deps

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/",
    response_model=chat_schemas.ChatQueryResponse,
    summary="Process Chat Query and Update Session",
    description=(
        "Receives a query and session_id. If the session is new, it's created. "
        "The query, response, sources, and a unique turn_query_id are appended to the session's record in the database. "
        "Retrieves context from Qdrant, generates an answer, and returns the answer with sources."
    ),
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during chat processing or session update"
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Chat service components or database unavailable"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Missing session_id or invalid request"
        },
    },
)
async def handle_chat_request(
    request: chat_schemas.ChatQueryRequest = Body(...),
    db: Session = Depends(deps.get_db_session),  # DB session is now crucial
):
    """
    Handles chat query, updates the corresponding ChatSession row with the new turn.
    """
    if not request.session_id:
        # This check could also be done by Pydantic if session_id is not Optional in ChatQueryRequest
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required field: session_id.",
        )

    if (
        not db
    ):  # Should be caught by dependency system if DB setup fails, but good to double check
        logger.error("Database session not available in chat endpoint.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is temporarily unavailable (database connection issue).",
        )

    logger.info(
        f"Received chat request for session: {request.session_id}. DB session present: {db is not None}"
    )

    try:
        # Pass DB session to the service for session creation/update and logging
        response = await chat_service.process_agent_query(request=request, db=db)

        # The error check below might be redundant if chat_service raises HTTPExceptions for critical errors
        # For example, if `answer` is the default error message.
        if (
            response.answer
            == "عذراً، حدث خطأ أثناء معالجة طلبك."  # Default error from service
            and not response.sources  # And no sources were found
            # Add more checks if the service returns a specific error structure
        ):
            logger.error(
                f"Chat service returned a default error message for query_id {response.query_id}, session {request.session_id}."
            )
            # This specific error indicates an issue within the service, likely already logged there.
            # The service should ideally raise an HTTPException itself if it's a server-side issue.
            # If it's a "no answer found" type of error, it might be a valid response.
            # For now, let's assume this signals an internal problem.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal error occurred while processing the chat request.",
            )

        return response

    except (
        HTTPException
    ):  # Re-raise HTTPExceptions directly (e.g., from _get_or_create_session)
        raise
    except RuntimeError as e:  # Catch critical service init errors if they propagate
        logger.critical(
            f"Critical runtime error reaching chat endpoint for session {request.session_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat service is currently unavailable: {e}",
        )
    except Exception as e:
        logger.exception(
            f"Unhandled exception during chat processing for session {request.session_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred: {type(e).__name__}",
        )
