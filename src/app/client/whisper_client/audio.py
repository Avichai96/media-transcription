"""Decode only enough audio to enforce the transcription duration limit."""

from io import BytesIO
from typing import BinaryIO

import av
import numpy as np
from numpy.typing import NDArray

from app.client.whisper_client.exceptions import (
    WhisperAudioTooLongError,
    WhisperInvalidMediaError,
)

SAMPLE_RATE = 16_000


class AudioDecoder:
    """Decode the first audio track as Whisper-compatible mono samples.

    Count resampled audio instead of trusting media duration metadata.
    """

    @staticmethod
    def decode(file: BinaryIO, max_seconds: int) -> NDArray[np.float32]:
        limit = max_seconds * SAMPLE_RATE
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        samples = 0
        with BytesIO() as pcm, av.open(file, mode="r") as container:
            if not container.streams.audio:
                raise WhisperInvalidMediaError("Upload media with an audio track.")
            for frame in container.decode(audio=0):
                frame.pts = None
                for converted in resampler.resample(frame):
                    samples = AudioDecoder._write_frame(
                        pcm, converted, samples, limit, max_seconds
                    )
            for converted in resampler.resample(None):
                samples = AudioDecoder._write_frame(
                    pcm, converted, samples, limit, max_seconds
                )
            audio = np.frombuffer(pcm.getvalue(), dtype=np.int16).astype(np.float32)

        if not samples:
            raise WhisperInvalidMediaError("The media contains no audio samples.")
        return audio / np.float32(32768)

    @staticmethod
    def _write_frame(
        pcm: BytesIO, frame: av.AudioFrame, count: int, limit: int, max_seconds: int
    ) -> int:
        count += frame.samples
        if count > limit:
            message = f"Audio exceeds the {max_seconds}-second limit."
            raise WhisperAudioTooLongError(message)
        pcm.write(frame.to_ndarray().tobytes())
        return count
