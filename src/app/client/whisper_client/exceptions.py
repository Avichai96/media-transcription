"""Errors at the boundary with the local Whisper engine."""


class WhisperClientError(Exception):
    """Report a failure in the Whisper client.

    The calling service decides how to present the failure.
    """


class WhisperInvalidMediaError(WhisperClientError):
    """Report unreadable media or missing audio samples.

    The caller can retry with a valid media file.
    """


class WhisperBusyError(WhisperClientError):
    """Report that the single inference slot is occupied.

    The caller can retry when the active transcription finishes.
    """


class WhisperAudioTooLongError(WhisperClientError):
    """Report that decoded audio exceeded the duration limit.

    Inference never starts for an overlong input.
    """
