"""Settings read from the environment, with the prefix SEEBAND_API_."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEEBAND_API_", frozen=True)

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    calc_workers: int = Field(default=2, ge=1)
    calc_timeout_s: float = Field(default=30.0, gt=0)
