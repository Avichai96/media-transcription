"""Validate uploads and coordinate media transcription."""

import logging
from typing import BinaryIO

from app.client.whisper_client.client import WhisperClient
from app.client.whisper_client.exceptions import (
    WhisperAudioTooLongError,
    WhisperBusyError,
    WhisperClientError,
    WhisperInvalidMediaError,
)
from app.modules.media.transcription_service.constants import MAX_UPLOAD_BYTES, MIB
from app.modules.media.transcription_service.exceptions import (
    AudioTooLongError,
    InvalidUploadError,
    TranscriptionBusyError,
    TranscriptionEngineError,
    UploadTooLargeError,
)
from app.modules.media.transcription_service.schema import TranscriptionResult
from app.modules.media.transcription_service.types import TranscriptionLanguage

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Apply media upload rules and request transcription.

    The Whisper client handles model execution and capacity.
    """

    def __init__(self, client: WhisperClient) -> None:
        self._client = client

    async def transcribe(
        self,
        file: BinaryIO,
        size: int | None,
        *,
        language: TranscriptionLanguage | None = None,
    ) -> TranscriptionResult:
        self._validate_upload(size)
        logger.info("event=transcription_started bytes=%s language=%s", size, language)
        try:
            text, output_language = await self._client.transcribe(
                file, language=language
            )
        except WhisperAudioTooLongError as error:
            logger.warning(
                "event=transcription_rejected reason=%s", type(error).__name__
            )
            raise AudioTooLongError(str(error)) from error
        except WhisperInvalidMediaError as error:
            logger.warning(
                "event=transcription_rejected reason=%s", type(error).__name__
            )
            raise InvalidUploadError(str(error)) from error
        except WhisperBusyError as error:
            logger.warning(
                "event=transcription_rejected reason=%s", type(error).__name__
            )
            raise TranscriptionBusyError(str(error)) from error
        except WhisperClientError as error:
            logger.warning(
                "event=transcription_rejected reason=%s", type(error).__name__
            )
            message = "The transcription engine failed."
            raise TranscriptionEngineError(message) from error
        return TranscriptionResult(text=text, language=output_language)

    @staticmethod
    def _validate_upload(size: int | None) -> None:
        if size is None or size == 0:
            logger.info("event=transcription_rejected reason=empty_upload")
            raise InvalidUploadError("Upload a non-empty media file.")
        if size > MAX_UPLOAD_BYTES:
            logger.info("event=transcription_rejected reason=upload_too_large")
            limit_mib = MAX_UPLOAD_BYTES // MIB
            raise UploadTooLargeError(f"Media files must be at most {limit_mib} MiB.")
