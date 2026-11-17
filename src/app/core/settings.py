"""Base model for the settings of the app and its clients."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    """Settings read from environment variables only, never from a file.

    Each field reads the environment variable named by its validation_alias.
    """

    model_config = SettingsConfigDict(
        frozen=True,
        env_ignore_empty=True,
        # Exact case stops validate_by_name from also reading $USER, $PORT and such.
        case_sensitive=True,
        validate_by_name=True,
        validate_by_alias=True,
    )
