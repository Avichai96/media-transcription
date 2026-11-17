"""Fix, format and check the code with `uv run format`; pre-commit runs it too."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Run each step even after one fails, then exit non-zero if any failed."""
    # Each Lambda ships alone and imports neither the app nor another Lambda, so
    # pylint compares each one's code only with its own.
    handlers = ROOT.glob("lambdas/*/handler.py")
    lambdas = sorted(str(path.parent.relative_to(ROOT)) for path in handlers)
    # Ruff fixes and formats; pylint then adds the two checks Ruff lacks,
    # duplicated code and modules longer than max-module-lines, and scripts/rules.py
    # the try/except in each layer and the reason for each module-level function.
    steps = [
        ["ruff", "check", "--fix"],
        ["ruff", "format"],
        ["pylint", "src", "scripts"],
        *(["pylint", path] for path in lambdas),
        ["scripts.rules"],
    ]
    failed: list[str] = []
    for step in steps:
        result = subprocess.run([sys.executable, "-m", *step], cwd=ROOT, check=False)
        if result.returncode:
            failed.append(" ".join(step))
    if failed:
        raise SystemExit(f"Failed: {'; '.join(failed)}")
