"""Schemas for the upload page service."""

from pydantic import BaseModel


class UploadLimits(BaseModel):
    """Describe what the transcription service accepts.

    The page shows these values so users see the limits before they upload.
    """

    max_upload_mib: int
    max_upload_bytes: int
    max_audio_seconds: int
