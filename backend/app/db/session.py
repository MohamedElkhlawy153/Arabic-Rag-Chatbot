from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
import logging

from ..core.config import settings
from .models import Base  # Import Base to create tables

logger = logging.getLogger(__name__)

engine = None
SessionLocal: Optional[sessionmaker[Session]] = None

if settings.SQLALCHEMY_DATABASE_URI:
    try:
        logger.info(
            f"Initializing SQLAlchemy engine for: {settings.SQLALCHEMY_DATABASE_URI[:settings.SQLALCHEMY_DATABASE_URI.find('@')] if '@' in settings.SQLALCHEMY_DATABASE_URI else settings.SQLALCHEMY_DATABASE_URI}"
        )  # Avoid logging password
        # Use pool_pre_ping=True for robustness against connection drops
        connect_args = {}
        if settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
            connect_args = {
                "check_same_thread": False
            }  # Required for SQLite usage with multiple threads/requests

        engine = create_engine(
            settings.SQLALCHEMY_DATABASE_URI,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("SQLAlchemy engine and session maker initialized.")

        # Create tables on startup if they don't exist
        logger.info("Creating database tables if they don't exist...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created.")

    except Exception as e:
        logger.error(f"Failed to initialize SQLAlchemy: {e}", exc_info=True)
        engine = None
        SessionLocal = None
else:
    logger.warning(
        "SQLALCHEMY_DATABASE_URI not set. Database features (logging/feedback to DB) will be disabled or limited."
    )


def get_db() -> Generator[Optional[Session], None, None]:
    """
    FastAPI dependency generator for obtaining a database session.
    Yields None if the database is not configured.
    """
    if SessionLocal is None:
        yield None
        return

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()  # Rollback in case of errors during request handling
        raise
    finally:
        db.close()
