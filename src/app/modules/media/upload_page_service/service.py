"""Business logic for the upload page service."""

from app.modules.media.transcription_service.constants import (
    MAX_AUDIO_SECONDS,
    MAX_UPLOAD_BYTES,
    MIB,
)
from app.modules.media.upload_page_service.schema import UploadLimits


class UploadPageService:
    """Describe the upload page for the browser.

    The page itself calls the transcription service for the actual work.
    """

    @staticmethod
    def limits() -> UploadLimits:
        return UploadLimits(
            max_upload_mib=MAX_UPLOAD_BYTES // MIB,
            max_upload_bytes=MAX_UPLOAD_BYTES,
            max_audio_seconds=MAX_AUDIO_SECONDS,
        )
