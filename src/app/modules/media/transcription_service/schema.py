"""Response schema for the transcription endpoint."""

from pydantic import BaseModel


class TranscriptionResult(BaseModel):
    """Return recognized text and the language used for transcription.

    The text may be empty when the model detects no speech.
    """

    text: str
    language: str
