"""Manage a local Whisper model and its inference capacity."""

import logging
from threading import Lock
from time import perf_counter
from typing import BinaryIO

from av.error import FFmpegError
from faster_whisper import WhisperModel
from starlette.concurrency import run_in_threadpool

from app.client.whisper_client.audio import SAMPLE_RATE, AudioDecoder
from app.client.whisper_client.config import TranscriptionSettings
from app.client.whisper_client.exceptions import (
    WhisperBusyError,
    WhisperClientError,
    WhisperInvalidMediaError,
)

logger = logging.getLogger(__name__)


class WhisperClient:
    """Own the local model and translate errors from its libraries.

    Model operations run off the event loop with one active transcription at a time.
    """

    def __init__(self, settings: TranscriptionSettings) -> None:
        started = perf_counter()
        self._max_audio_seconds = settings.max_audio_seconds
        self._inference_lock = Lock()
        try:
            self._model = WhisperModel(
                settings.model_id,
                device=settings.device,
                compute_type=settings.compute_type,
                cpu_threads=settings.cpu_threads,
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise WhisperClientError("Could not load the Whisper model.") from error

        logger.info(
            "event=model_loaded model=%s device=%s "
            "compute_type=%s elapsed_seconds=%.3f",
            settings.model_id,
            settings.device,
            settings.compute_type,
            perf_counter() - started,
        )

    async def transcribe(
        self, file: BinaryIO, *, language: str | None = None
    ) -> tuple[str, str]:
        try:
            result = await run_in_threadpool(self._transcribe, file, language)
        except RuntimeError as error:
            raise WhisperClientError("Whisper inference failed.") from error
        return result

    async def aclose(self) -> None:
        try:
            await run_in_threadpool(self._unload)
        except RuntimeError as error:
            raise WhisperClientError("Could not unload the Whisper model.") from error

        logger.info("event=model_unloaded")

    def _transcribe(self, file: BinaryIO, language: str | None) -> tuple[str, str]:
        if not self._inference_lock.acquire(blocking=False):
            raise WhisperBusyError("A transcription is already running.")

        started = perf_counter()
        try:
            try:
                audio = AudioDecoder.decode(file, self._max_audio_seconds)
            except (FFmpegError, ValueError) as error:
                message = "Upload readable media with an audio track."
                raise WhisperInvalidMediaError(message) from error

            decoded = perf_counter()
            # The VAD filter drops silence, where Whisper tends to hallucinate text.
            segments, info = self._model.transcribe(
                audio, task="transcribe", language=language, vad_filter=True
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            logger.info(
                "event=transcription_completed audio_seconds=%.3f "
                "decode_seconds=%.3f inference_seconds=%.3f language=%s empty=%s",
                len(audio) / SAMPLE_RATE,
                decoded - started,
                perf_counter() - decoded,
                info.language,
                not bool(text),
            )
            return text, info.language
        finally:
            self._inference_lock.release()

    def _unload(self) -> None:
        with self._inference_lock:
            self._model.model.unload_model()
