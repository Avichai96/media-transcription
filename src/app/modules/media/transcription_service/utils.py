"""Pure helpers for the transcription service; keep database access in repository.py."""

from app.core.exceptions import (
    AppError,
    BadRequestError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    TooManyRequestsError,
    UnprocessableContentError,
)
from app.modules.media.transcription_service.constants import RETRY_AFTER_SECONDS
from app.modules.media.transcription_service.exceptions import (
    AudioTooLongError,
    InvalidUploadError,
    TranscriptionBusyError,
    TranscriptionError,
    TranscriptionNotFoundError,
    UploadTooLargeError,
)


class ErrorMapper:
    """Translate transcription errors into HTTP errors.

    Every route that calls the service shares this mapping, so statuses never drift.
    """

    @staticmethod
    def to_app_error(error: TranscriptionError) -> AppError:
        message = str(error)
        if isinstance(error, UploadTooLargeError):
            return PayloadTooLargeError(message)
        if isinstance(error, AudioTooLongError):
            return UnprocessableContentError(message)
        if isinstance(error, InvalidUploadError):
            return BadRequestError(message)
        if isinstance(error, TranscriptionBusyError):
            return TooManyRequestsError(message, retry_after=RETRY_AFTER_SECONDS)
        if isinstance(error, TranscriptionNotFoundError):
            return NotFoundError(message)
        return ServiceUnavailableError(message)
