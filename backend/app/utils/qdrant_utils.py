# backend/app/utils/qdrant_utils.py
import logging
from typing import Optional
import qdrant_client
from qdrant_client.http import models as qdrant_models

from ..core.config import settings

logger = logging.getLogger(__name__)

_qdrant_client: Optional[qdrant_client.QdrantClient] = None


def get_qdrant_client() -> qdrant_client.QdrantClient:
    """Initializes and returns a singleton Qdrant client instance."""
    global _qdrant_client
    if _qdrant_client is None:
        logger.info("Initializing Qdrant client...")
        try:
            if settings.QDRANT_URL:
                logger.info(f"Connecting to Qdrant server at: {settings.QDRANT_URL}")
                _qdrant_client = qdrant_client.QdrantClient(
                    url=str(settings.QDRANT_URL),
                    api_key=settings.QDRANT_API_KEY,
                    prefer_grpc=False,
                    timeout=60,
                )
            elif settings.QDRANT_LOCATION:
                logger.info(
                    f"Using local Qdrant storage at: {settings.QDRANT_LOCATION}"
                )
                _qdrant_client = qdrant_client.QdrantClient(
                    location=settings.QDRANT_LOCATION
                )
            else:
                raise ValueError(
                    "QDRANT_LOCATION or QDRANT_URL must be set in settings."
                )

            # Ensure the collection exists
            try:
                collection_info = _qdrant_client.get_collection(
                    collection_name=settings.QDRANT_COLLECTION_NAME
                )
                logger.info(
                    f"Using existing Qdrant collection: '{settings.QDRANT_COLLECTION_NAME}'"
                )
                # Optional: Validate vector size if possible?
                # vector_params = collection_info.vectors_config.params
                # if vector_params.size != settings.VECTOR_DIMENSION:
                #      logger.error(f"Mismatch! Qdrant collection dim ({vector_params.size}) != config dim ({settings.VECTOR_DIMENSION})")
                #      raise ValueError("Qdrant collection dimension mismatch.")
            except Exception:
                logger.info(
                    f"Collection '{settings.QDRANT_COLLECTION_NAME}' not found. Creating..."
                )
                _qdrant_client.recreate_collection(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    vectors_config=qdrant_models.VectorParams(
                        size=settings.VECTOR_DIMENSION,
                        distance=qdrant_models.Distance.COSINE,  # Or DOT
                    ),
                )
                logger.info(f"Collection '{settings.QDRANT_COLLECTION_NAME}' created.")

            logger.info("Qdrant client initialized successfully.")

        except Exception as e:
            logger.critical(
                f"Failed to initialize Qdrant client or collection: {e}", exc_info=True
            )
            _qdrant_client = None  # Ensure it's None on failure
            raise RuntimeError("Could not initialize Qdrant client") from e

    return _qdrant_client
