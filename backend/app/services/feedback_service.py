# backend/app/services/feedback_service.py

import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..db import models  # Import DB models
from ..schemas import feedback as feedback_schemas

logger = logging.getLogger(__name__)


async def store_feedback(
    feedback_data: feedback_schemas.FeedbackRequest,
    db: Session = None,  # db is now required by the endpoint
) -> bool:
    """
    Stores feedback for a specific turn within a ChatSession.
    It finds the ChatSession by session_id, then locates the turn by query_id
    and updates the feedback_values list at the corresponding index.

    Args:
        feedback_data (feedback_schemas.FeedbackRequest): Validated feedback data containing
                                                           session_id, query_id, and rating.
        db (Session): SQLAlchemy database session (required).

    Returns:
        bool: True if storage was successful, False otherwise.
    """
    session_id = feedback_data.session_id
    turn_query_id = feedback_data.query_id  # The ID of the specific Q/A turn
    rating = feedback_data.rating  # 0 or 1

    log_message = (
        f"Attempting to store feedback for SessionID={session_id}, "
        f"TurnQueryID={turn_query_id}, Rating={rating}. "
        f"Comment='{feedback_data.comment[:50] if feedback_data.comment else 'N/A'}'"
    )
    logger.info(log_message)

    try:
        # 1. Fetch the ChatSession
        chat_session = (
            db.query(models.ChatSession)
            .filter(models.ChatSession.session_id == session_id)
            .first()
        )

        if not chat_session:
            logger.warning(
                f"ChatSession with session_id '{session_id}' not found. Cannot store feedback for turn '{turn_query_id}'."
            )
            return False

        # 2. Find the index of the turn_query_id in the session's query_ids list
        try:
            # Ensure query_ids is a list (it should be due to model default)
            if not isinstance(chat_session.query_ids, list):
                logger.error(
                    f"ChatSession {session_id} has invalid query_ids (not a list). Feedback aborted."
                )
                # This indicates a data corruption or bug in session creation/update
                return False

            turn_index = chat_session.query_ids.index(turn_query_id)
        except ValueError:
            logger.warning(
                f"Turn with query_id '{turn_query_id}' not found in ChatSession '{session_id}'. "
                f"Available query_ids: {chat_session.query_ids}. Cannot store feedback."
            )
            return False

        # 3. Update the feedback_values list at the found index
        # Ensure feedback_values is a list of the same length as query_ids
        if not isinstance(chat_session.feedback_values, list) or len(
            chat_session.feedback_values
        ) != len(chat_session.query_ids):
            logger.error(
                f"ChatSession {session_id} has mismatched feedback_values list "
                f"(len {len(chat_session.feedback_values) if chat_session.feedback_values else 'None'}) "
                f"vs query_ids (len {len(chat_session.query_ids)}). Re-initializing feedback_values."
            )
            # Attempt to repair: initialize feedback_values with Nones
            chat_session.feedback_values = [None] * len(chat_session.query_ids)
            # It's crucial that chat_service correctly initializes and maintains these lists.

        # Now, update the specific feedback value
        current_feedback_list = list(
            chat_session.feedback_values
        )  # Create a mutable copy
        current_feedback_list[turn_index] = rating
        chat_session.feedback_values = current_feedback_list  # Assign the new list back

        db.add(chat_session)  # Mark as dirty
        db.commit()
        logger.info(
            f"Feedback for session '{session_id}', turn '{turn_query_id}' (index {turn_index}) "
            f"updated to {rating} successfully."
        )

        return True

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Failed to store feedback in ChatSession {session_id} (DB error): {e}",
            exc_info=True,
        )
        return False
    except (
        Exception
    ) as e:  # Catch other potential errors (e.g., list manipulation if data is malformed)
        db.rollback()
        logger.error(
            f"An unexpected error occurred during feedback storage for session {session_id}: {e}",
            exc_info=True,
        )
        return False
