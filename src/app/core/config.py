"""Application settings, read from environment variables only."""

from enum import StrEnum

from pydantic import Field

from app.core.settings import EnvSettings


class Environment(StrEnum):
    """Where the app runs; each has its settings and secrets in environment/<value>/."""

    LOCAL = "local"
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class Settings(EnvSettings):
    """Every setting the app itself reads from its environment."""

    environment: Environment = Field(
        default=Environment.LOCAL, validation_alias="APP_ENV"
    )
    app_name: str = Field(default="media-transcription", validation_alias="APP_NAME")
    debug: bool = Field(default=False, validation_alias="DEBUG")


settings = Settings()
