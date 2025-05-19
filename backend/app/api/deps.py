# backend/app/api/deps.py

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging
from qdrant_client import QdrantClient

from ..core.config import settings
from ..core import security
from ..db.session import get_db as get_db_session_gen
from ..utils.qdrant_utils import get_qdrant_client

# This function now returns the Cohere wrapper instance
from ..utils.embeddings import get_embedding_model
from ..utils.qdrant_utils import get_qdrant_client as get_raw_qdrant_client
from langchain_qdrant import QdrantVectorStore  # Keep this import
from ..schemas.auth import TokenData


logger = logging.getLogger(__name__)

_langchain_qdrant_instance: Optional[QdrantVectorStore] = None

# OAuth2 scheme for token authentication
# The tokenUrl should point to your actual login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_langchain_qdrant() -> QdrantVectorStore:
    """
    Dependency function to get an initialized LangChain Qdrant vector store object.
    Uses the underlying Qdrant client and embedding model dependencies.
    Now implicitly uses Cohere embeddings via get_embedding_model().
    """
    global _langchain_qdrant_instance
    if _langchain_qdrant_instance is None:
        logger.info(
            "Initializing LangChain Qdrant wrapper instance (with Cohere Embeddings)..."
        )
        try:
            # Get the dependencies needed by the wrapper
            qdrant_cli = get_qdrant_client()
            # This now returns an instance of CohereLangchainEmbeddings
            embedding_mod = get_embedding_model()

            # Create the LangChain wrapper instance
            _langchain_qdrant_instance = QdrantVectorStore(
                client=qdrant_cli,
                collection_name=settings.QDRANT_COLLECTION_NAME,
                embedding=embedding_mod,  # Pass the Cohere wrapper object
            )
            logger.info(
                "LangChain Qdrant wrapper initialized successfully (using Cohere)."
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize LangChain Qdrant wrapper (with Cohere): {e}",
                exc_info=True,
            )
            _langchain_qdrant_instance = None
            raise RuntimeError("Could not initialize LangChain Qdrant wrapper") from e

    return _langchain_qdrant_instance


def get_db_session() -> Generator[Optional[Session], None, None]:
    yield from get_db_session_gen()


# --- Authentication Dependencies ---
async def get_current_user_token_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Decodes JWT token and returns TokenData if valid.
    Raises HTTPException for invalid tokens.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = security.decode_access_token(token)
    if payload is None:
        logger.warning(f"Token decoding failed or token is invalid.")
        raise credentials_exception

    username: Optional[str] = payload.get(
        "sub"
    )  # 'sub' is standard for subject (username)
    if username is None:
        logger.warning(f"Username (sub) not found in token payload.")
        raise credentials_exception

    return TokenData(username=username)


async def get_current_active_admin(
    current_user_token: TokenData = Depends(get_current_user_token_data),
) -> TokenData:
    """
    Ensures the authenticated user is the configured admin.
    This can be expanded for role-based access control.
    """
    # For now, we only have one hardcoded admin.
    # If you had roles, you'd check current_user_token.roles or fetch user details.
    if current_user_token.username != settings.ADMIN_USERNAME:
        logger.warning(
            f"User '{current_user_token.username}' attempted an admin action but is not the configured admin."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action.",
        )
    logger.info(f"Admin user '{current_user_token.username}' authorized for action.")
    return current_user_token


# This function needs implementation if you require agent authentication
def get_current_agent_dep() -> str:
    # Placeholder: Implement actual agent authentication (e.g., from API key header)
    logger.warning(
        "Using placeholder agent ID 'agent_007'. Implement actual authentication."
    )
    return "agent_007"  # Replace with real logic


def get_current_agent() -> str:
    return get_current_agent_dep()


def get_qdrant_client() -> QdrantClient:  # Expose the raw client
    return get_raw_qdrant_client()
