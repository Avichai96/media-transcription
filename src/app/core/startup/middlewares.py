"""The middlewares every request passes through."""

from fastapi import FastAPI


def add_middlewares(app: FastAPI) -> None:
    """Add every middleware to app; the last one added is the first to see a request."""
