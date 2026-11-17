"""Serve the htmx upload page and the result fragment it requests."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.exceptions import AppError
from app.modules.media.transcription_service.exceptions import TranscriptionError
from app.modules.media.transcription_service.router import ServiceDep
from app.modules.media.transcription_service.types import TranscriptionLanguage
from app.modules.media.transcription_service.upload_route import UploadRoute
from app.modules.media.transcription_service.utils import ErrorMapper
from app.modules.media.upload_page_service.constants import TEMPLATES_DIR
from app.modules.media.upload_page_service.service import UploadPageService

templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(prefix="/upload", tags=["upload page"], route_class=UploadRoute)

PageServiceDep = Annotated[UploadPageService, Depends()]


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request, service: PageServiceDep) -> HTMLResponse:
    context = {
        "limits": service.limits(),
        "action": request.url_for("transcription_fragment").path,
    }
    return templates.TemplateResponse(request, "index.html", context)


@router.post("/transcriptions", response_class=HTMLResponse, include_in_schema=False)
async def transcription_fragment(
    request: Request,
    file: Annotated[UploadFile, File()],
    service: ServiceDep,
    language: Annotated[TranscriptionLanguage | None, Form()] = None,
) -> HTMLResponse:
    try:
        result = await service.transcribe(file.file, file.size, language=language)
    except TranscriptionError as error:
        # Errors stay JSON; static/app.js shows their message in the page's alert.
        app_error: AppError = ErrorMapper.to_app_error(error)
        raise app_error from error
    context = {
        "text": result.text,
        "language": result.language,
        "filename": file.filename,
    }
    return templates.TemplateResponse(request, "_result.html", context)
