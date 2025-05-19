# backend/app/utils/embeddings.py

import logging
from typing import Optional, List, Generator
from tenacity import retry, stop_after_attempt, wait_exponential  # For robustness

# --- LangChain Core Import ---
from langchain_core.embeddings import Embeddings

import cohere  # Cohere API client

# --- Local Imports ---
from ..core.config import settings
from .cohere_utils import get_cohere_client  # Import Cohere client getter

logger = logging.getLogger(__name__)

# --- Cohere LangChain Embeddings Wrapper ---


class CohereLangchainEmbeddings(Embeddings):
    """
    LangChain Embeddings wrapper for Cohere API.
    Handles batching and specifies input types.
    """

    client: cohere.Client  # Use synchronous client here
    model: str = settings.COHERE_EMBED_MODEL
    batch_size: int = settings.COHERE_EMBED_BATCH_SIZE
    embed_type: str = "float"  # Or other types like "int8", "ubinary" if needed

    def __init__(self, client: cohere.Client):
        super().__init__()
        if client is None:
            raise ValueError("Cohere client cannot be None")
        self.client = client

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _embed_batch(self, texts: List[str], input_type: str) -> List[List[float]]:
        """Embeds a batch of texts using Cohere API with retries."""
        try:
            response = self.client.embed(
                texts=texts,
                model=self.model,
                input_type=input_type,
                embedding_types=[self.embed_type],
            )
            # Assuming embed_type is 'float' for now
            if hasattr(response.embeddings, self.embed_type):
                embeddings = getattr(response.embeddings, self.embed_type)
                # Ensure the output is List[List[float]]
                if embeddings and isinstance(embeddings[0], list):
                    return embeddings
                else:
                    logger.error(
                        f"Cohere embed did not return expected list of lists for type '{self.embed_type}'. Got: {type(embeddings)}"
                    )
                    raise TypeError("Unexpected embedding format from Cohere.")
            else:
                logger.error(
                    f"Cohere response missing expected embedding type: {self.embed_type}"
                )
                raise ValueError(
                    f"Cohere response missing {self.embed_type} embeddings"
                )

        except cohere.ApiException as e:
            logger.error(f"Cohere API error during batch embedding: {e}")
            raise  # Re-raise after logging for retry logic
        except Exception as e:
            logger.error(
                f"Unexpected error during Cohere batch embedding: {e}", exc_info=True
            )
            raise  # Re-raise for retry logic

    def _generate_batches(
        self, texts: List[str], batch_size: int
    ) -> Generator[List[str], None, None]:
        """Yields batches of texts."""
        for i in range(0, len(texts), batch_size):
            yield texts[i : i + batch_size]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of documents using Cohere API with batching.
        Uses 'search_document' input type.
        """
        logger.debug(
            f"Embedding {len(texts)} documents with Cohere model {self.model}..."
        )
        all_embeddings: List[List[float]] = []
        batch_count = 0
        for batch in self._generate_batches(texts, self.batch_size):
            batch_count += 1
            logger.debug(
                f"Processing document batch {batch_count} (size {len(batch)})..."
            )
            batch_embeddings = self._embed_batch(batch, input_type="search_document")
            all_embeddings.extend(batch_embeddings)

        logger.debug(f"Finished embedding {len(texts)} documents.")
        if len(all_embeddings) != len(texts):
            logger.error(
                f"Mismatch in document embedding count: expected {len(texts)}, got {len(all_embeddings)}"
            )
            # Handle this error appropriately - maybe raise?
            raise ValueError("Embedding count mismatch after batching.")
        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        Embeds a single query using Cohere API.
        Uses 'search_query' input type.
        """
        logger.debug(f"Embedding query with Cohere model {self.model}...")
        # Embed as a single-item batch
        embeddings = self._embed_batch([text], input_type="search_query")
        if not embeddings or len(embeddings) != 1:
            logger.error(
                f"Failed to embed query or received unexpected result count: {text[:50]}..."
            )
            raise ValueError("Failed to embed query correctly.")
        logger.debug("Finished embedding query.")
        return embeddings[0]


# --- Singleton Instance ---
_embedding_model: Optional[CohereLangchainEmbeddings] = None


def get_embedding_model() -> CohereLangchainEmbeddings:
    """Loads the Cohere embedding model wrapper (Singleton)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info(
            f"Initializing Cohere Embeddings wrapper for model: {settings.COHERE_EMBED_MODEL}"
        )
        try:
            cohere_client = get_cohere_client()  # Get the initialized client
            _embedding_model = CohereLangchainEmbeddings(client=cohere_client)

            # Test query
            _test_text = "اختبار"  # Arabic test text
            _test_emb = _embedding_model.embed_query(_test_text)
            emb_len = len(_test_emb)
            logger.info(f"Cohere embedding wrapper loaded successfully. Dim: {emb_len}")

            # Validate dimension
            if emb_len != settings.VECTOR_DIMENSION:
                logger.critical(
                    f"CRITICAL MISMATCH: Cohere model '{settings.COHERE_EMBED_MODEL}' returned dimension ({emb_len}) != configured VECTOR_DIMENSION ({settings.VECTOR_DIMENSION}). Collection creation/search will fail!"
                )
                # Optionally raise an error to prevent startup with bad config
                # raise ValueError("Embedding dimension mismatch between Cohere model and settings.")
            else:
                logger.info(
                    f"Embedding dimension ({emb_len}) matches configured dimension ({settings.VECTOR_DIMENSION})."
                )

        except Exception as e:
            logger.error(
                f"Failed to initialize Cohere embeddings wrapper: {e}",
                exc_info=True,
            )
            _embedding_model = None  # Ensure reset on failure
            # Re-raise critical error
            raise RuntimeError(f"Could not initialize Cohere embeddings: {e}")
    return _embedding_model
