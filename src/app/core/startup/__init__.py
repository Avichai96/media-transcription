"""What main.py sets up around the app: its lifespan and its middlewares."""

from app.core.startup.lifespan import lifespan
from app.core.startup.middlewares import add_middlewares

__all__ = ["add_middlewares", "lifespan"]
