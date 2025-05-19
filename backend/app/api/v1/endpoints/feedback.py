from fastapi import APIRouter, Depends, HTTPException, status, Body
import logging

from ....schemas import feedback as feedback_schemas
from ....schemas import common as common_schemas
from ....services import feedback_service
from ....api import deps  # Import dependency functions
from sqlalchemy.orm import Session  # Import type hint

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/",
    response_model=common_schemas.StandardResponse,
    status_code=status.HTTP_201_CREATED,  # Or HTTP_200_OK if just updating
    summary="Submit Feedback for a Chat Turn",
    description=(
        "Allows submission of feedback (rating 0 or 1) for a specific query-response turn "
        "within a given chat session. The feedback is recorded in the main ChatSession table."
    ),
)
async def submit_feedback(
    request: feedback_schemas.FeedbackRequest = Body(...),
    db: Session = Depends(deps.get_db_session),
) -> common_schemas.StandardResponse:
    """
    Receives and stores feedback for a specific chat turn within a session.
    Updates the `feedback_values` list in the `ChatSession` row.
    """
    logger.info(
        f"Received feedback submission for session_id: {request.session_id}, "
        f"query_id: {request.query_id}, rating: {request.rating}"
    )

    if not db:  # Should be caught by dependency system
        logger.error(
            "Feedback submission failed: Database is not configured or available."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback storage is currently unavailable (database connection issue).",
        )

    # Attempt to store feedback using the service
    success = await feedback_service.store_feedback(feedback_data=request, db=db)

    if success:
        return common_schemas.StandardResponse(
            detail="Feedback submitted and recorded successfully.", success=True
        )
    else:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,  # Or 500 if it's definitely a server/DB write error
            detail="Failed to store feedback. Session or query ID might not exist, or a database error occurred.",
        )
