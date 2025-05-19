# backend/app/main.py
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

# from .llm_loader import load_qwen_model_and_tokenizer, cleanup_llm_resources
from .utils.embeddings import get_embedding_model
from .utils.qdrant_utils import get_qdrant_client
from .api.v1 import routes as v1_routes
from .core.config import settings
from .core.logging_config import setup_logging

# Setup logging ASAP
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager. Initializes essential clients on startup.
    """
    logger.info("Application startup sequence initiated...")
    app.state.start_time = time.time()

    # 1. Initialize Embedding Model (Cohere)
    try:
        # This now initializes the Cohere embedding wrapper via get_embedding_model
        app.state.embedding_model = get_embedding_model()
        logger.info("Embedding model (Cohere) initialized successfully.")
    except Exception as e:
        logger.critical(
            f"CRITICAL: Failed to initialize Embedding Model on startup: {e}",
            exc_info=True,
        )
        # Decide if the app can run without embeddings - likely not for RAG.
        raise RuntimeError("Embedding model initialization failed") from e

    # 2. Initialize Qdrant Client
    try:
        app.state.qdrant_client = get_qdrant_client()
        logger.info("Qdrant client initialized successfully.")
    except Exception as e:
        logger.critical(
            f"CRITICAL: Failed to initialize Qdrant Client on startup: {e}",
            exc_info=True,
        )
        raise RuntimeError("Qdrant client initialization failed") from e

    # 3. LLM Initialization (Lazy Loading)
    # Generation LLMs (Gemini or fallback Qwen3) are initialized lazily
    # within their respective utility functions (get_gemini_model, get_qwen_model)
    # when first needed by the chat service. No eager loading here.
    logger.info("Generation LLM will be loaded lazily on first request.")

    logger.info("Application startup sequence complete.")
    yield  # Application runs
    # --- Shutdown ---
    logger.info("Application shutdown sequence initiated...")

    # --- Cleanup (If Needed) ---
    # Qwen3 cleanup is commented out as it's not loaded eagerly
    # cleanup_llm_resources()
    # Cohere/Gemini clients managed by their respective libraries, often no explicit cleanup needed.
    # Qdrant client might not need explicit cleanup depending on setup.
    # Add any other specific cleanup here if required.
    # --- End Cleanup ---

    duration = time.time() - app.state.start_time
    logger.info(f"Application shutdown complete. Uptime: {duration:.2f} seconds.")


# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,  # Updated name from config
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version="1.2.0",  # Consider bumping version for significant changes
    # --- Updated Description ---
    description=(
        "Backend API for an Arabic RAG Chatbot Assistant using Cohere for embeddings/reranking, "
        "Qdrant as the vector store, and primarily Google Gemini for generation "
        "(with Qwen3 as a potential fallback/alternative)."
    ),
    # --- End Updated Description ---
    lifespan=lifespan,
)


# --- Middleware ---
# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=(
            [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
            if isinstance(settings.BACKEND_CORS_ORIGINS, list)
            else []
        ),
        allow_origin_regex=(
            settings.BACKEND_CORS_ORIGINS
            if isinstance(settings.BACKEND_CORS_ORIGINS, str)
            and settings.BACKEND_CORS_ORIGINS != "*"
            else None
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    log_details = {
        "method": request.method,
        "url": str(request.url),
        "client": request.client.host if request.client else "unknown",
    }
    logger.info("Request received", extra=log_details)
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000
        log_details["status_code"] = response.status_code
        log_details["duration_ms"] = round(duration_ms, 2)
        logger.info("Request completed", extra=log_details)
        response.headers["X-Process-Time"] = str(duration_ms / 1000)
        return response
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        log_details["status_code"] = 500
        log_details["duration_ms"] = round(duration_ms, 2)
        log_details["error"] = type(e).__name__
        logger.error(
            "Request failed with unhandled exception", extra=log_details, exc_info=True
        )
        return JSONResponse(
            status_code=500, content={"detail": "Internal Server Error"}
        )


# --- API Routers ---
app.include_router(v1_routes.api_router, prefix=settings.API_V1_STR)
logger.info(f"Included API router at prefix: {settings.API_V1_STR}")


# --- Root Endpoint ---
@app.get("/", tags=["Health Check"], summary="Health Check Endpoint")
async def read_root(start_time: float = Depends(lambda: app.state.start_time)):
    """Basic health check endpoint."""
    uptime = time.time() - start_time

    return {
        "status": "OK",
        "message": f"Welcome to {settings.PROJECT_NAME}!",
        "version": app.version,
        "uptime_seconds": round(uptime, 2),
    }
