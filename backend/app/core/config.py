# backend/app/core/config.py

import os
import json
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List, Optional, Union

# Import field_validator from Pydantic V2
from pydantic import Field, field_validator, AnyHttpUrl, ValidationInfo

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PROJECT_NAME: str = (
        "Arabic RAG Chatbot Backend (Cohere+Qwen3+Qdrant)"  # Updated name
    )
    API_V1_STR: str = "/api/v1"

    # --- JWT Authentication Settings ---
    # These will be loaded from .env if present, otherwise defaults are used.
    SECRET_KEY: str = Field(
        default="a_very_secret_strong_key_for_dev_only_change_me", env="SECRET_KEY"
    )
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24, env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )  # Default 1 day

    # --- Admin User (Hardcoded credentials loaded from .env) ---
    ADMIN_USERNAME: str = Field(default="admin", env="ADMIN_USERNAME")
    ADMIN_PASSWORD: str = Field(default="securepassword123", env="ADMIN_PASSWORD")

    # --- Cohere Settings ---
    COHERE_API_KEY: Optional[str] = Field(None, env="COHERE_API_KEY")
    COHERE_EMBED_MODEL: str = Field("embed-multilingual-v3.0")
    COHERE_RERANK_MODEL: str = Field("rerank-multilingual-v3.0")
    COHERE_EMBED_BATCH_SIZE: int = Field(96)  # Max batch size for co.embed v3

    # --- Google Gemini Settings (Generation LLM) --- NEW ---
    GEMINI_API_KEY: Optional[str] = Field(None, env="GEMINI_API_KEY")
    GEMINI_GENERATION_MODEL: str = Field("gemini-1.5-flash-latest")

    # --- Generation Parameters (Applicable to active LLM - Gemini or Qwen) ---
    GENERATION_TEMPERATURE: float = Field(
        0.7,
        description="Controls randomness (0.0-1.0 for Gemini, potentially higher for others)",
    )
    GENERATION_TOP_P: float = Field(0.95, description="Nucleus sampling parameter")
    GENERATION_TOP_K: Optional[int] = Field(
        None, description="Top-K sampling parameter (Gemini uses this)"
    )
    GENERATION_MAX_OUTPUT_TOKENS: int = Field(
        1024, description="Max tokens in the generated response"
    )  # <-- IT IS HERE!

    # --- Qdrant Settings ---
    QDRANT_LOCATION: Optional[str] = Field(":memory:")  # Default to local storage
    QDRANT_URL: Optional[AnyHttpUrl] = Field(None)  # Optional server URL
    QDRANT_API_KEY: Optional[str] = Field(None)  # Optional API key for Qdrant server
    QDRANT_COLLECTION_NAME: str = Field(
        "arabic_cohere_qwen3_kb"
    )  # Updated collection name
    # Dimension for Cohere embed-multilingual-v3.0 is 1024
    VECTOR_DIMENSION: int = Field(
        1024, description="Dimension MUST match Cohere embedding model"
    )
    # --- End Qdrant Settings ---

    # --- LLM Settings (Qwen3) ---
    # Select the specific Qwen model you are using
    QWEN_MODEL_NAME: str = Field("Qwen/Qwen3-0.6B")
    GENERATION_MODEL_DEVICE: str = Field("auto")  # e.g., "auto", "cuda", "cpu"
    # Directory for storing/caching Hugging Face models
    LOCAL_MODELS_DIR: str = Field("./models")  # Adjust path as needed
    # --- End LLM Settings ---

    # --- Qwen3 Generation Parameters ---
    ENABLE_THINKING: bool = Field(False)  # Qwen specific, maybe remove if not used
    THINKING_TEMP: float = Field(0.6)  # Qwen specific
    THINKING_TOP_P: float = Field(0.95)  # Qwen specific
    NON_THINKING_TEMP: float = Field(0.7)  # Used in current Qwen generation logic
    NON_THINKING_TOP_P: float = Field(0.8)  # Used in current Qwen generation logic
    # THINKING_PRESENCE_PENALTY: float = Field(1.1) # Removed as not used in latest code
    # NON_THINKING_PRESENCE_PENALTY: float = Field(1.1) # Removed as not used in latest code
    MAX_NEW_TOKENS: int = Field(1024)  # Max tokens for LLM generation
    # --- End Qwen3 Parameters ---

    # --- RAG Retrieval & Reranking ---
    RETRIEVER_K: int = Field(
        10, description="Number of initial documents to retrieve before reranking"
    )
    RERANK_TOP_N: int = Field(
        3, description="Number of documents to keep after Cohere reranking"
    )
    # --- End RAG Settings ---

    # --- Text Splitting ---
    CHUNK_SIZE: int = Field(900)
    CHUNK_OVERLAP: int = Field(100)
    # --- End Text Splitting ---

    # --- Database Settings ---
    SQLALCHEMY_DATABASE_URI: Optional[str] = Field(
        "sqlite:///./chatbot_backend_cohere_qwen3.db"  # Updated DB name
    )
    # --- End Database Settings ---

    # --- CORS Settings ---
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = '["http://localhost:3000"]'
    # --- End CORS Settings ---

    # --- Validators ---
    # Use model_validator for CORS as it depends on the raw input string
    # Or keep @validator with pre=True if that works reliably
    @field_validator(
        "BACKEND_CORS_ORIGINS", mode="before"
    )  # Use 'before' mode for pre-processing
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        # This logic remains the same
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return [i.strip() for i in v.split(",") if i.strip()]
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError(
            "BACKEND_CORS_ORIGINS must be a list of strings or a comma-separated string"
        )

    # --- Use @field_validator for Pydantic V2 style ---
    @field_validator(
        "COHERE_API_KEY", "GEMINI_API_KEY", mode="after"
    )  # Use 'after' (default) or 'plain'
    def check_api_keys(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Checks if API keys are set and logs a warning if not."""
        field_name = info.field_name
        if not v:
            logger.warning(
                f"{field_name} is not set in environment variables or .env file. "
                f"Features depending on it will be unavailable."
            )
        return v

    # --- End Pydantic V2 Validator ---

    # --- Use @field_validator for Pydantic V2 style ---
    @field_validator(
        "QDRANT_LOCATION", "QDRANT_URL", mode="after"
    )  # Use 'after' (default) or 'plain'
    def check_qdrant_config(
        cls, v: Optional[Union[str, AnyHttpUrl]], info: ValidationInfo
    ) -> Optional[Union[str, AnyHttpUrl]]:
        """Basic check for Qdrant config (example)."""
        location = info.data.get("QDRANT_LOCATION")
        url = info.data.get("QDRANT_URL")
        # Add more sophisticated validation if necessary
        # Example: Check if BOTH are set, which might be ambiguous
        # if location and url:
        #     logger.warning("Both QDRANT_LOCATION and QDRANT_URL are set. QDRANT_URL will likely take precedence.")
        return v

    # --- End Pydantic V2 Validator ---

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create the singleton settings instance
settings = Settings()
