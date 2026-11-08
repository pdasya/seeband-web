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
    # The planned machine has 2 vCPUs.
    fit_max_running: int = Field(default=2, ge=1)
    fit_max_waiting: int = Field(default=4, ge=0)
    fit_timeout_s: float = Field(default=60.0, gt=0)
    fit_max_per_client: int = Field(default=2, ge=1)
    # A file's text is limited to 2000000 characters, which UTF-8 holds in at most 8 MB.
    max_body_bytes: int = Field(default=10_000_000, ge=1)
    # A fit's time grows with its points, about 6 to 11 ms for each point on one Mac.
    max_points: int = Field(default=2000, ge=1)
    # Per client. A slider sends many cheap curves, and a fit can take a minute.
    calc_per_minute: int = Field(default=600, ge=1)
    band_diagram_per_minute: int = Field(default=600, ge=1)
    parse_per_minute: int = Field(default=60, ge=1)
    guess_per_minute: int = Field(default=60, ge=1)
    fit_per_minute: int = Field(default=30, ge=1)
    # Addresses whose `X-Forwarded-For` the server believes. `python -m seeband_api` only.
    trusted_proxies: str = "127.0.0.1,::1"
