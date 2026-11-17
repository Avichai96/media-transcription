"""Accept file uploads for transcription."""

from http import HTTPStatus
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.core.exceptions import AppError
from app.modules.media.transcription_service.exceptions import TranscriptionError
from app.modules.media.transcription_service.schema import TranscriptionResult
from app.modules.media.transcription_service.service import TranscriptionService
from app.modules.media.transcription_service.types import TranscriptionLanguage
from app.modules.media.transcription_service.upload_route import UploadRoute
from app.modules.media.transcription_service.utils import ErrorMapper

router = APIRouter(
    prefix="/transcriptions", tags=["transcriptions"], route_class=UploadRoute
)


def get_transcription_service(request: Request) -> TranscriptionService:
    return cast("TranscriptionService", request.state.transcription_service)


ServiceDep = Annotated[TranscriptionService, Depends(get_transcription_service)]


@router.post(
    "",
    responses={
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE: {"description": "Upload is too large"},
        HTTPStatus.UNPROCESSABLE_ENTITY: {
            "description": "Invalid upload or audio duration"
        },
    },
)
async def transcribe(
    file: Annotated[UploadFile, File()],
    service: ServiceDep,
    language: Annotated[
        TranscriptionLanguage | None,
        Form(description="Spoken language. Omit to detect automatically."),
    ] = None,
) -> TranscriptionResult:
    try:
        result = await service.transcribe(file.file, file.size, language=language)
    except TranscriptionError as error:
        app_error: AppError = ErrorMapper.to_app_error(error)
        raise app_error from error
    return result
