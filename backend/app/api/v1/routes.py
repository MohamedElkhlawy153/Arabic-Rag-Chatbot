# backend/app/api/v1/routes.py

from fastapi import APIRouter
from .endpoints import (
    chat,
    feedback,
    upload,
    auth,
    admin_kb,
)  # Import the new upload router

api_router = APIRouter()
"""Main router for API version 1."""
# Authentication
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Admin - Knowledge Base
# All endpoints under this router will be prefixed with /api/v1/admin/knowledge-base
api_router.include_router(
    admin_kb.router,
    prefix="/admin/knowledge-base",
    tags=["Admin - Knowledge Base Management"],
)
api_router.include_router(chat.router, prefix="/chat", tags=["Chat Agent Assistant"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(
    upload.router, prefix="/upload", tags=["File Upload (Session)"]
)
