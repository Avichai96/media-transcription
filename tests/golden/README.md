# Golden transcription evaluation

Run from the project root:

```bash
RUN_GOLDEN_TESTS=1 DEBUG=false uv run --locked python -m unittest tests.test_golden -v
```

The test runs the actual upload API with a real model and decoder. It replaces the
service dependency to load the explicitly configured evaluation checkpoint once.
Application lifespan startup and the browser UI are covered separately.

## Reproducibility

The manifest pins Small to Hugging Face commit
`536b0662742c02347bc0e980a01041f333bce120`.
CPU, INT8 and four threads are fixed. The implementation uses VAD and the
application's decoding parameters. uv.lock fixes the package versions.
Each downloaded recording must match its SHA-256 hash before use.
Downloads are cached only after verification. Delete a damaged cached file
to download it again. Never replace a stored hash just to make a test pass.

The report at `.cache/last-run.json` records model revision, package versions,
platform, references, predictions, elapsed times and per-case quality outcomes.
It is overwritten each run. Timing is informational because hardware and load
affect it. The report can contain partial results if a run fails.

## Cases and acceptance

Every speech recording is run with an explicit language and with automatic
language detection. A case passes only if its language is correct, its transcript
is nonempty and its WER is within the manifest threshold.

| Recording | Reference source | Maximum WER | Required |
| --- | --- | --- | --- |
| JFK English speech | OpenAI Whisper tests | 0.15 | yes |
| Hebrew bridge sentence | Tatoeba audio 567161 | 0.20 | yes |
| Hebrew relationship question | Tatoeba audio 238678 | 0.20 | yes |
| Hebrew tennis sentence | Tatoeba audio 238623 | 0.30 | yes |
| Hebrew iPod sentence | Tatoeba audio 238677 | 0.25 | diagnostic |
| Hebrew tongue twister, non-native speaker | Wikimedia / Wiktionary | 0.25 | diagnostic |

These thresholds were selected before the expanded evaluation using the earlier
Small comparison. They permit at most three English word edits, one edit on the
six-word Hebrew sentences, and two edits on the seven-word tennis sentence.
The four-word iPod diagnostic permits one edit.

Diagnostic cases expose previously observed model limitations. Their quality
failures are written as `accepted: false`, even when unittest passes.
HTTP failures and fixture hash failures always fail the test, including diagnostics.
The diagnostics must become required cases only through an explicit review of
model quality and the intended product requirements.

Six generated silence cases cover one and five seconds, each with English,
Hebrew and automatic language selection. Every case must return empty text.

WER ignores case, punctuation and combining marks such as Hebrew niqqud.
It counts substitutions, insertions and deletions, and can exceed 1.
Blank speech output is always a failure.

## Sources and limitations

- English recording: https://github.com/openai/whisper/blob/main/tests/jfk.flac
- Hebrew sentences and recordings: https://tatoeba.org/en/audio/index/heb
- Tongue-twister reference: https://en.wiktionary.org/wiki/User:Dvortygirl/dicho#Hebrew
- Audio: https://commons.wikimedia.org/wiki/File:He-US-dicho-saying.ogg

The repository stores references and download URLs. Audio files stay in the
ignored cache. Observe the source terms when redistributing recordings.
This set has one English speaker and several short Hebrew examples. It does not
establish broad accuracy for noisy speech, long recordings or mixed languages.
Add independent recordings and reviewed references before making such claims.
