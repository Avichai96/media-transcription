"""Run one transcription through the real model; opt in with RUN_MODEL_TESTS=1."""

import io
import os
import wave
from unittest import IsolatedAsyncioTestCase, skipUnless

from httpx import ASGITransport, AsyncClient

from app.client.whisper_client.client import WhisperClient
from app.client.whisper_client.config import TranscriptionSettings
from app.main import app
from app.modules.media.transcription_service.router import get_transcription_service
from app.modules.media.transcription_service.service import TranscriptionService

URL = "/media/transcriptions"


@skipUnless(os.environ.get("RUN_MODEL_TESTS") == "1", "set RUN_MODEL_TESTS=1")  # noqa: TID251
class RealModelTests(IsolatedAsyncioTestCase):
    """Load the configured model, which downloads it on first use."""

    async def test_transcribes_a_short_clip(self) -> None:
        output = io.BytesIO()
        with wave.open(output, "wb") as recording:
            recording.setparams((1, 2, 16_000, 0, "NONE", "not compressed"))
            recording.writeframes(b"\x00\x00" * 16_000)

        service = TranscriptionService(WhisperClient(TranscriptionSettings()))
        app.dependency_overrides[get_transcription_service] = lambda: service
        self.addCleanup(app.dependency_overrides.pop, get_transcription_service)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            response = await http.post(
                URL, files={"file": ("silence.wav", output.getvalue())}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json()["text"], str)
