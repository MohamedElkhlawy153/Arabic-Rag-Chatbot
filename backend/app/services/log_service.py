# backend/app/services/log_service.py

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import json

from ..db import models

logger = logging.getLogger(__name__)


def log_generic_event_to_db(
    db: Optional[Session],
    event_type: str,
    status: Optional[str] = "INFO",
    details: Optional[str] = None,
    component_id: Optional[str] = None,
    related_id: Optional[str] = None,
    latency_ms: Optional[float] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Logs a generic event entry to the GenericEventLog table in the database.
    """
    if not db:
        logger.warning(
            f"Database session not available. Skipping DB logging for event: {event_type}"
        )
        return

    try:
        log_entry = models.GenericEventLog(
            event_type=event_type,
            status=status.upper() if status else None,  # Store status in uppercase
            details=details,
            component_id=component_id,
            related_id=related_id,
            latency_ms=latency_ms,
            extra_data=extra_data,  # SQLAlchemy's JSON type handles serialization
        )
        db.add(log_entry)
        db.flush()
        logger.debug(
            f"Generic log entry prepared for DB: {event_type}, status: {status}"
        )

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to log generic event '{event_type}' to database: {e}",
            exc_info=True,
        )
        # Rollback should be handled by the caller if this is part of a larger transaction
    except Exception as e:
        logger.error(
            f"Unexpected error logging generic event '{event_type}' to DB: {e}",
            exc_info=True,
        )
