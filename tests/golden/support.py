"""Reproducible fixture loading and evaluation metrics for golden tests."""

import hashlib
import io
import re
import unicodedata
import wave
from pathlib import Path

from httpx import AsyncClient


class WordErrorRate:
    """Compare normalized reference and predicted words.

    Keep lexical errors while ignoring punctuation, case and combining marks.
    """

    @staticmethod
    def words(text: str) -> list[str]:
        normalized = "".join(
            char
            for char in unicodedata.normalize("NFKD", text.casefold())
            if unicodedata.category(char) != "Mn"
        )
        return re.findall(r"[^\W_]+", normalized)

    @staticmethod
    def edits(reference: str, prediction: str) -> int:
        expected = WordErrorRate.words(reference)
        actual = WordErrorRate.words(prediction)
        previous = list(range(len(actual) + 1))
        for index, word in enumerate(expected, 1):
            current = [index]
            for column, candidate in enumerate(actual, 1):
                current.append(
                    min(
                        previous[column] + 1,
                        current[-1] + 1,
                        previous[column - 1] + (word != candidate),
                    )
                )
            previous = current
        return previous[-1]

    @staticmethod
    def score(reference: str, prediction: str) -> float:
        return WordErrorRate.edits(reference, prediction) / max(
            1, len(WordErrorRate.words(reference))
        )


class GoldenFixtures:
    """Load hash-verified public recordings and generate silence.

    Cache only verified downloads so interrupted retrieval cannot poison the cache.
    """

    @staticmethod
    async def load(case: dict, cache: Path) -> bytes:
        path = cache / case["file"]
        if path.exists():
            data = path.read_bytes()
        else:
            async with AsyncClient(follow_redirects=True) as http:
                response = await http.get(case["url"], timeout=30)
                response.raise_for_status()
                data = response.content
        if hashlib.sha256(data).hexdigest() != case["sha256"]:
            raise ValueError(f"Fixture hash mismatch: {case['file']}")
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
        return data

    @staticmethod
    def silence(seconds: int) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as recording:
            recording.setparams((1, 2, 16_000, 0, "NONE", "not compressed"))
            recording.writeframes(b"\x00\x00" * 16_000 * seconds)
        return output.getvalue()
