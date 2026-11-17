"""The app's lifespan, which starts what it needs and closes its clients."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from app.client.whisper_client.client import WhisperClient
from app.client.whisper_client.config import TranscriptionSettings
from app.client.whisper_client.exceptions import WhisperClientError
from app.modules.media.transcription_service.service import TranscriptionService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[dict[str, TranscriptionService]]:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    client: WhisperClient | None = None
    try:
        settings = TranscriptionSettings()
        client = await run_in_threadpool(WhisperClient, settings)
        yield {"transcription_service": TranscriptionService(client)}
    except WhisperClientError:
        logger.exception("Whisper failed during application lifespan.")
        raise
    finally:
        if client is not None:
            try:
                await client.aclose()
            except WhisperClientError:
                logger.exception("Whisper cleanup failed.")
