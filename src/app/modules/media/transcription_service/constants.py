"""Limits for the transcription service, read once from the environment."""

from app.client.whisper_client.config import TranscriptionSettings

MIB = 1024 * 1024

_settings = TranscriptionSettings()

MAX_UPLOAD_BYTES = _settings.max_upload_mib * MIB

# Leave room for multipart boundaries and headers above the file limit.
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 64 * 1024

# Seconds a client should wait before retrying after a 429.
RETRY_AFTER_SECONDS = _settings.retry_after_seconds

# Shown on the upload page so users know the limits before they upload.
MAX_AUDIO_SECONDS = _settings.max_audio_seconds
