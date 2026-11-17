"""Routes for the media module; each service router is mounted here."""

from fastapi import APIRouter

from app.modules.media.transcription_service.router import (
    router as transcription_router,
)
from app.modules.media.upload_page_service.router import router as upload_page_router

router = APIRouter(prefix="/media")

router.include_router(transcription_router)
router.include_router(upload_page_router)
