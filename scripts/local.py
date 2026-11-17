"""Build and run the stack in compose.yaml: `uv run local-build`, `uv run local-run`."""

import os
import sys
from pathlib import Path

# compose.yaml sits in the project root, whichever directory `uv run` starts in.
ROOT = Path(__file__).resolve().parents[1]


def build() -> None:
    """Build the images; arguments go on to `docker compose build`, e.g. --no-cache."""
    _compose("build")


def run() -> None:
    """Start the stack; arguments go on to `docker compose up`, e.g. --build or -d."""
    _compose("up")


def dev() -> None:
    """Build and start the development stack with Python source reload enabled."""
    _compose(
        "up",
        "--build",
        "--watch",
        compose_files=("compose.yaml", "compose.dev.yaml"),
    )


def debug() -> None:
    """Run the host server with reload and wait for the IDE debugger on port 5678."""
    os.chdir(ROOT)
    os.execvp(
        "uv",
        [
            "uv",
            "run",
            "--locked",
            "--group",
            "debug",
            "--env-file",
            "environment/local/local.config.env",
            "--env-file",
            "environment/local/local.secret.env",
            "python",
            "-m",
            "debugpy",
            "--listen",
            "127.0.0.1:5678",
            "--wait-for-client",
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--reload",
            "--reload-dir",
            "src",
            *sys.argv[1:],
        ],
    )


def _compose(
    command: str, *arguments: str, compose_files: tuple[str, ...] = ()
) -> None:
    os.chdir(ROOT)
    # Compose takes over this process, so Ctrl+C reaches it and it stops the stack.
    files = [argument for path in compose_files for argument in ("-f", path)]
    os.execvp(
        "docker", ["docker", "compose", *files, command, *arguments, *sys.argv[1:]]
    )
