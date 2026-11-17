"""Settings for local Whisper inference."""

from typing import Literal

from pydantic import Field

from app.core.settings import EnvSettings


class TranscriptionSettings(EnvSettings):
    """Configure the model, its hardware and the accepted upload sizes.

    The model identifier can name any faster-whisper compatible Hugging Face
    repository.
    """

    model_id: str = Field(
        default="Systran/faster-whisper-small",
        min_length=1,
        validation_alias="TRANSCRIPTION_MODEL_ID",
    )
    device: Literal["cpu", "cuda", "auto"] = Field(
        default="cpu", validation_alias="TRANSCRIPTION_DEVICE"
    )
    compute_type: str = Field(
        default="int8", min_length=1, validation_alias="TRANSCRIPTION_COMPUTE_TYPE"
    )
    cpu_threads: int = Field(
        default=4, ge=0, validation_alias="TRANSCRIPTION_CPU_THREADS"
    )
    max_audio_seconds: int = Field(
        default=120, gt=0, validation_alias="TRANSCRIPTION_MAX_AUDIO_SECONDS"
    )
    max_upload_mib: int = Field(
        default=25, gt=0, validation_alias="TRANSCRIPTION_MAX_UPLOAD_MIB"
    )
    retry_after_seconds: int = Field(
        default=10, gt=0, validation_alias="TRANSCRIPTION_RETRY_AFTER_SECONDS"
    )
