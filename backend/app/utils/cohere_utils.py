# backend/app/utils/cohere_utils.py (NEW FILE)

import logging
import cohere
from typing import Optional

from ..core.config import settings

logger = logging.getLogger(__name__)

_cohere_client: Optional[cohere.Client] = None


def get_cohere_client() -> cohere.Client:
    """Initializes and returns a singleton Cohere client instance."""
    global _cohere_client
    if _cohere_client is None:
        if not settings.COHERE_API_KEY:
            logger.error("COHERE_API_KEY is not configured.")
            raise ValueError("Cohere API Key not found in settings.")

        logger.info("Initializing Cohere client...")
        try:
            # Using Client which is synchronous for embedding/rerank simplicity here
            # Use AsyncClient if integrating into async routes directly
            _cohere_client = cohere.Client(
                api_key=settings.COHERE_API_KEY,
                # Optional: Add timeout, retries etc.
                # timeout=60
            )
            # Optional: Test connection (e.g., small embed call) - skipped for brevity
            logger.info("Cohere client initialized successfully.")

        except Exception as e:
            logger.critical(f"Failed to initialize Cohere client: {e}", exc_info=True)
            _cohere_client = None  # Ensure it's None on failure
            raise RuntimeError("Could not initialize Cohere client") from e

    return _cohere_client
