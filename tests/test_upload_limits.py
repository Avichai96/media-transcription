"""Exercise uploads without downloading a Whisper checkpoint."""

import io
import wave
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import av
from httpx import ASGITransport, AsyncClient

from app.client.whisper_client.client import WhisperClient
from app.client.whisper_client.config import TranscriptionSettings
from app.main import app
from app.modules.media.transcription_service.router import get_transcription_service
from app.modules.media.transcription_service.service import TranscriptionService

URL = "/media/transcriptions"


class TranscriptionUploadTests(IsolatedAsyncioTestCase):
    """Exercise FastAPI's parser and the real decoder with a stub model.

    Each test gets a separate inference client and transport.
    """

    async def asyncSetUp(self) -> None:
        with patch("app.client.whisper_client.client.WhisperModel") as model:
            self.inference = model.return_value.transcribe
            self.inference.return_value = (
                [SimpleNamespace(text="hello")],
                SimpleNamespace(language="en"),
            )
            service = TranscriptionService(
                WhisperClient(
                    TranscriptionSettings(model_id="unused", max_audio_seconds=1)
                )
            )
        app.dependency_overrides[get_transcription_service] = lambda: service
        self.addCleanup(app.dependency_overrides.pop, get_transcription_service)
        self.http = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )
        self.addAsyncCleanup(self.http.aclose)

    async def test_oversized_content_length_rejected_before_reading_body(self) -> None:
        async def unexpected_body():
            self.fail("The application tried to read the oversized request.")
            yield b""

        response = await self.http.post(
            URL,
            headers={"Content-Length": str(30 * 1024 * 1024)},
            content=unexpected_body(),
        )

        self.assertEqual(response.status_code, 413)
        self.inference.assert_not_called()

    async def test_streamed_body_stops_at_limit_and_next_upload_succeeds(self) -> None:
        async def chunks():
            yield (
                b'--limit\r\nContent-Disposition: form-data; name="file"; '
                b'filename="sample.wav"\r\n\r\n'
            )
            yield b"x" * (1024 * 1024 + 100)
            yield b"x" * (1024 * 1024)
            self.fail("The application read past the rejected body chunk.")

        with patch(
            "app.modules.media.transcription_service.upload_route.MAX_REQUEST_BYTES",
            2 * 1024 * 1024,
        ):
            response = await self.http.post(
                URL,
                headers={"Content-Type": "multipart/form-data; boundary=limit"},
                content=chunks(),
            )

        self.assertEqual(response.status_code, 413)
        self.inference.assert_not_called()
        self.assertEqual(
            (
                await self.http.post(URL, files={"file": ("ok.wav", self._wav(800))})
            ).status_code,
            200,
        )

    async def test_file_limit_excludes_multipart_overhead(self) -> None:
        with patch(
            "app.modules.media.transcription_service.service.MAX_UPLOAD_BYTES", 5
        ):
            response = await self.http.post(URL, files={"file": ("bad.wav", b"x" * 6)})

        self.assertEqual(response.status_code, 413)
        self.inference.assert_not_called()

    async def test_duration_boundary_rejects_before_inference_and_releases_slot(
        self,
    ) -> None:
        too_long = await self.http.post(
            URL, files={"file": ("long.wav", self._wav(16_001))}
        )
        self.assertEqual(too_long.status_code, 422)
        self.assertIn("1-second limit", too_long.json()["detail"])
        self.inference.assert_not_called()

        exact = await self.http.post(
            URL, files={"file": ("exact.wav", self._wav(16_000))}
        )
        self.assertEqual(exact.status_code, 200)
        self.assertEqual(exact.json(), {"text": "hello", "language": "en"})
        self.inference.assert_called_once()

    async def test_omitting_language_uses_auto_detection(self) -> None:
        response = await self.http.post(
            URL, files={"file": ("sample.wav", self._wav(800))}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.inference.call_args.kwargs["language"])

    async def test_requested_language_reaches_whisper(self) -> None:
        for language in ("he", "en"):
            with self.subTest(language=language):
                response = await self.http.post(
                    URL,
                    files={"file": ("sample.wav", self._wav(800))},
                    data={"language": language},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.inference.call_args.kwargs["language"], language)
                self.assertEqual(self.inference.call_args.kwargs["task"], "transcribe")

    async def test_unsupported_language_is_rejected_before_inference(self) -> None:
        response = await self.http.post(
            URL,
            files={"file": ("sample.wav", self._wav(800))},
            data={"language": "fr"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "language"])
        self.inference.assert_not_called()

    async def test_upload_page_and_assets_are_served(self) -> None:
        page = await self.http.get("/media/upload")
        self.assertEqual(page.status_code, 200)
        self.assertIn('hx-post="/media/upload/transcriptions"', page.text)
        root = await self.http.get("/")
        self.assertEqual(root.status_code, 307)
        self.assertEqual(root.headers["location"], "/media/upload")
        for asset in ("/static/htmx.min.js", "/static/app.js", "/static/app.css"):
            self.assertEqual((await self.http.get(asset)).status_code, 200)

    async def test_htmx_fragment_renders_escaped_transcript(self) -> None:
        self.inference.return_value = (
            [SimpleNamespace(text="<b>hi</b>")],
            SimpleNamespace(language="en"),
        )
        response = await self.http.post(
            "/media/upload/transcriptions", files={"file": ("a.wav", self._wav(800))}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("&lt;b&gt;hi&lt;/b&gt;", response.text)
        self.assertNotIn("<b>hi</b>", response.text)

    async def test_htmx_fragment_errors_stay_json(self) -> None:
        response = await self.http.post(
            "/media/upload/transcriptions", files={"file": ("junk.wav", b"nope" * 50)}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    async def test_corrupt_media_returns_400_before_inference(self) -> None:
        response = await self.http.post(
            URL, files={"file": ("junk.wav", b"this is not media" * 100)}
        )

        self.assertEqual(response.status_code, 400)
        self.inference.assert_not_called()

    async def test_empty_file_returns_400(self) -> None:
        response = await self.http.post(URL, files={"file": ("empty.wav", b"")})

        self.assertEqual(response.status_code, 400)
        self.inference.assert_not_called()

    async def test_media_without_audio_track_returns_400(self) -> None:
        response = await self.http.post(
            URL, files={"file": ("silent.mp4", self._video_only())}
        )

        self.assertEqual(response.status_code, 400)
        self.inference.assert_not_called()

    async def test_busy_engine_returns_429_with_retry_after(self) -> None:
        client = app.dependency_overrides[get_transcription_service]()._client
        self.assertTrue(client._inference_lock.acquire(blocking=False))
        self.addCleanup(client._inference_lock.release)

        response = await self.http.post(URL, files={"file": ("ok.wav", self._wav(800))})

        self.assertEqual(response.status_code, 429)
        self.assertIn("retry-after", response.headers)
        self.inference.assert_not_called()

    @staticmethod
    def _video_only() -> bytes:
        output = io.BytesIO()
        with av.open(output, mode="w", format="mp4") as container:
            stream = container.add_stream("mpeg4", rate=5)
            stream.width, stream.height, stream.pix_fmt = 64, 64, "yuv420p"
            for _ in range(5):
                frame = av.VideoFrame(64, 64, "yuv420p")
                container.mux(stream.encode(frame))
            container.mux(stream.encode())
        return output.getvalue()

    @staticmethod
    def _wav(samples: int) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as recording:
            recording.setparams((1, 2, 16_000, 0, "NONE", "not compressed"))
            recording.writeframes(b"\x00\x00" * samples)
        return output.getvalue()
