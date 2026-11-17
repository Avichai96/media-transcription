"""Errors raised by the transcription service; routes map each to an HTTP error."""

from app.modules.media.transcription_service.types import TranscriptionId


class TranscriptionError(Exception):
    """Base of the transcription service's errors, which carry no HTTP status.

    Catch it to handle any of them; a route maps each to one of core/exceptions.
    """


class TranscriptionNotFoundError(TranscriptionError):
    """Raised when no transcription has the requested id.

    A route reports it as a 404 with this message.
    """

    def __init__(self, transcription_id: TranscriptionId) -> None:
        super().__init__(f"Transcription {transcription_id} not found")


class InvalidUploadError(TranscriptionError):
    """Report an invalid media upload.

    The route returns the validation message to the caller.
    """


class TranscriptionBusyError(TranscriptionError):
    """Indicate that inference capacity is occupied.

    A caller can retry once the active job finishes.
    """


class TranscriptionEngineError(TranscriptionError):
    """Indicate that the local model failed during inference.

    The original error is available to server-side logging.
    """


class AudioTooLongError(TranscriptionError):
    """Report media that exceeds the allowed audio duration.

    The route returns the duration limit to the caller.
    """


class UploadTooLargeError(TranscriptionError):
    """Report an uploaded file above the allowed byte size.

    The route returns the file size limit to the caller.
    """
