# backend/app/utils/gemini_utils.py

import logging
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions  # Import google exceptions
from typing import Optional

from ..core.config import settings

logger = logging.getLogger(__name__)

_gemini_model_instance: Optional[genai.GenerativeModel] = None


def get_gemini_model(system_instruction: str) -> genai.GenerativeModel:
    """Initializes and returns a singleton Gemini GenerativeModel instance."""
    global _gemini_model_instance
    if _gemini_model_instance is None:
        if not settings.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY is not configured.")
            raise ValueError("Gemini API Key not found in settings.")

        logger.info(
            f"Initializing Google Gemini model: {settings.GEMINI_GENERATION_MODEL}"
        )
        try:
            # Configure the SDK
            genai.configure(api_key=settings.GEMINI_API_KEY)

            # Create the model instance
            _gemini_model_instance = genai.GenerativeModel(
                model_name=settings.GEMINI_GENERATION_MODEL,
                system_instruction=system_instruction,
                # Safety settings can be configured here if needed
                # safety_settings=[...]
            )
            # Optional: Simple test call - skipped for brevity
            logger.info("Google Gemini model initialized successfully.")

        except google_exceptions.GoogleAPIError as e:
            logger.critical(
                f"Failed to initialize Google Gemini client (API Error): {e}",
                exc_info=True,
            )
            _gemini_model_instance = None
            raise RuntimeError("Could not initialize Google Gemini client") from e
        except Exception as e:
            logger.critical(
                f"Failed to initialize Google Gemini client (Other Error): {e}",
                exc_info=True,
            )
            _gemini_model_instance = None
            raise RuntimeError("Could not initialize Google Gemini client") from e

    return _gemini_model_instance
