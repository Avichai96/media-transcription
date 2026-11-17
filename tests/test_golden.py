"""Evaluate the real model against fixed speech references and silence."""

import json
import logging
import platform
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest import IsolatedAsyncioTestCase, TestCase, skipUnless

from httpx import ASGITransport, AsyncClient
from huggingface_hub import snapshot_download
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from app.client.whisper_client.client import WhisperClient
from app.client.whisper_client.config import TranscriptionSettings
from app.core.settings import EnvSettings
from app.main import app
from app.modules.media.transcription_service.router import get_transcription_service
from app.modules.media.transcription_service.service import TranscriptionService
from tests.golden.support import GoldenFixtures, WordErrorRate


class GoldenSettings(EnvSettings):
    """Control real-model evaluation independently of fast tests.

    Enable explicitly because fixtures and model weights may need downloading.
    """

    enabled: bool = Field(default=False, validation_alias="RUN_GOLDEN_TESTS")


@skipUnless(GoldenSettings().enabled, "set RUN_GOLDEN_TESTS=1")
class GoldenTests(IsolatedAsyncioTestCase):
    """Exercise the public upload endpoint using a real Small checkpoint.

    Download fixtures into an ignored cache and verify their content hashes.
    """

    async def test_golden_transcriptions(self) -> None:
        directory = Path(__file__).parent / "golden"
        manifest = json.loads((directory / "manifest.json").read_text())
        cache = directory / ".cache"
        cache.mkdir(exist_ok=True)
        model = manifest["model"]
        snapshot = await run_in_threadpool(
            snapshot_download,
            model["repository"],
            revision=model["revision"],
            allow_patterns=[
                "model.bin",
                "config.json",
                "tokenizer.json",
                "vocabulary.txt",
                "vocabulary.json",
                "preprocessor_config.json",
            ],
        )
        settings = TranscriptionSettings(
            model_id=snapshot,
            device=model["device"],
            compute_type=model["compute_type"],
            cpu_threads=model["cpu_threads"],
            max_audio_seconds=120,
        )
        client = await run_in_threadpool(WhisperClient, settings)
        self.addAsyncCleanup(client.aclose)
        service = TranscriptionService(client)
        app.dependency_overrides[get_transcription_service] = lambda: service
        self.addCleanup(app.dependency_overrides.pop, get_transcription_service)
        report = {
            "model": model,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "packages": {
                name: version(name)
                for name in ("faster-whisper", "ctranslate2", "av", "onnxruntime")
            },
            "results": [],
            "silence_results": [],
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            for case in manifest["cases"]:
                with self.subTest(fixture=case["id"]):
                    data = await GoldenFixtures.load(case, cache)
                    for mode in case["modes"]:
                        with self.subTest(case=case["id"], mode=mode):
                            started = perf_counter()
                            response = await http.post(
                                "/media/transcriptions",
                                files={"file": (case["file"], data)},
                                data={"language": case["language"]}
                                if mode == "explicit"
                                else {},
                            )
                            elapsed = perf_counter() - started
                            self.assertEqual(response.status_code, 200, response.text)
                            result = response.json()
                            errors = WordErrorRate.edits(
                                case["reference"], result["text"]
                            )
                            words = len(WordErrorRate.words(case["reference"]))
                            score = errors / words
                            accepted = (
                                score <= case["max_wer"]
                                and result["language"] == case["language"]
                                and bool(result["text"].strip())
                            )
                            report["results"].append(
                                {
                                    "id": case["id"],
                                    "mode": mode,
                                    "gate": case["gate"],
                                    "reference": case["reference"],
                                    **result,
                                    "expected_language": case["language"],
                                    "wer": score,
                                    "word_errors": errors,
                                    "reference_words": words,
                                    "max_wer": case["max_wer"],
                                    "accepted": accepted,
                                    "elapsed_seconds": elapsed,
                                }
                            )
                            (cache / "last-run.json").write_text(
                                json.dumps(report, ensure_ascii=False, indent=2)
                            )
                            logging.getLogger(__name__).warning(
                                "golden_case=%s mode=%s wer=%.3f accepted=%s gate=%s",
                                case["id"],
                                mode,
                                score,
                                accepted,
                                case["gate"],
                            )
                            if case["gate"]:
                                self.assertTrue(accepted, report["results"][-1])
            for seconds in (1, 5):
                for language in ("en", "he", None):
                    with self.subTest(silence_seconds=seconds, language=language):
                        response = await http.post(
                            "/media/transcriptions",
                            files={
                                "file": ("silence.wav", GoldenFixtures.silence(seconds))
                            },
                            data={"language": language} if language else {},
                        )
                        self.assertEqual(response.status_code, 200, response.text)
                        empty = response.json()["text"].strip() == ""
                        report["silence_results"].append(
                            {
                                "seconds": seconds,
                                "requested_language": language,
                                "accepted": empty,
                            }
                        )
                        (cache / "last-run.json").write_text(
                            json.dumps(report, ensure_ascii=False, indent=2)
                        )
                        self.assertTrue(empty, response.json())


class WordErrorRateTests(TestCase):
    """Check the metric independently of model predictions.

    Known edits guard against an accidentally permissive golden test.
    """

    def test_normalization(self) -> None:
        self.assertEqual(WordErrorRate.score("Hello, WORLD!", "hello world"), 0)
        self.assertEqual(WordErrorRate.score("שָׁלוֹם", "שלום"), 0)

    def test_empty_and_insertion_heavy_transcripts(self) -> None:
        self.assertEqual(WordErrorRate.score("", ""), 0)
        self.assertEqual(WordErrorRate.score("one two", ""), 1)
        self.assertEqual(WordErrorRate.score("one", "one two three"), 2)

    def test_word_edits(self) -> None:
        self.assertEqual(WordErrorRate.score("one two", "one three"), 0.5)
        self.assertEqual(WordErrorRate.score("one two", "one"), 0.5)
        self.assertEqual(WordErrorRate.score("one two", "one two three"), 0.5)


class GoldenFixtureTests(IsolatedAsyncioTestCase):
    """Validate the fixture trust boundary without model inference.

    Corrupt cached audio must fail before it reaches the application.
    """

    async def test_corrupt_cached_recording_is_rejected(self) -> None:
        manifest = json.loads(
            (Path(__file__).parent / "golden" / "manifest.json").read_text()
        )
        case = manifest["cases"][0]
        with TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / case["file"]).write_bytes(b"damaged recording")
            with self.assertRaisesRegex(ValueError, "Fixture hash mismatch"):
                await GoldenFixtures.load(case, cache)
