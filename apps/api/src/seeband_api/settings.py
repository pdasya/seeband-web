"""Settings read from the environment, with the prefix SEEBAND_API_."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The most values a request's list of points can hold, whatever `max_points` says.
MAX_LISTED_POINTS = 100_000
# What a body of numbers needs for each point a setting allows: 3 quantities, 2 lists of a point,
# and a value in up to 24 characters with its comma. A request's other fields fit in the margin.
_BYTES_PER_POINT = 3 * 2 * 25
_BODY_MARGIN_BYTES = 64_000
DEFAULT_JSON_BODY_BYTES = 1_000_000


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
    # A file's text is limited to 2000000 characters, which UTF-8 holds in at most 8 MB. This is
    # the limit of `POST /api/parse` and of any route not in `max_json_body_bytes`.
    max_body_bytes: int = Field(default=10_000_000, ge=1)
    # Calc, fit, guess and band-diagram hold numbers, not a file: 3 quantities of 2000 points, each
    # value in up to 24 characters, take about 300 KB. A larger body is refused before it is read.
    # Unset, it is 1 MB, or what `max_points` needs if more. Set lower, the server warns at start.
    max_json_body_bytes: int | None = Field(default=None, ge=1)
    # A fit's time grows with its points, about 6 to 11 ms for each point on one Mac. It cannot pass
    # `request_checks.MAX_LISTED_POINTS`, the most a request's list can hold.
    max_points: int = Field(default=2000, ge=1, le=MAX_LISTED_POINTS)
    # Per client. A slider sends many cheap curves, and a fit can take a minute.
    calc_per_minute: int = Field(default=600, ge=1)
    band_diagram_per_minute: int = Field(default=600, ge=1)
    parse_per_minute: int = Field(default=60, ge=1)
    guess_per_minute: int = Field(default=60, ge=1)
    fit_per_minute: int = Field(default=30, ge=1)
    # Addresses whose `X-Forwarded-For` the server believes. `python -m seeband_api` only.
    trusted_proxies: str = "127.0.0.1,::1"

    @property
    def json_body_bytes(self) -> int:
        """The body limit of calc, fit, guess and band-diagram: as set, or what points need."""
        if self.max_json_body_bytes is not None:
            return self.max_json_body_bytes
        return max(DEFAULT_JSON_BODY_BYTES, self.json_body_bytes_needed)

    @property
    def json_body_bytes_needed(self) -> int:
        """What a body of `max_points` for each quantity can take. A smaller limit set by hand
        refuses some fits within `max_points` with a 413, before their clearer `too_many_points`."""
        return self.max_points * _BYTES_PER_POINT + _BODY_MARGIN_BYTES
