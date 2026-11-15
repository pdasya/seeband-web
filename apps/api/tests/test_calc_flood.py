"""A14 acceptance, through a real server: one address floods, another keeps its answers fast.

The flooder runs heavy calcs of 1000 points (about 0.7 s each on one Mac) and parses of the largest
text (about 2.5 s) from many loops for 8 s, as one address could within raised rates. The other
address asks for light curves throughout.
"""

import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx2
from running_server import free_port, running_server
from seeband_core.model_catalog import registry
from seeband_core.model_scales import default_start

_MODE = registry.get("dpb").describe().fit_mode("dpb_s_rho")
_CURVE = {
    "model": "dpb",
    "fit_mode": "dpb_s_rho",
    "scattering": "acPh",
    "parameters": default_start(_MODE),
    "min_temperature_k": 50.0,
    "max_temperature_k": 800.0,
}
HEAVY = {**_CURVE, "points": 1000}
LIGHT = {**_CURVE, "points": 20}
# 2 MB of text the parser reads line by line, the most a parse may take.
LARGEST_PARSE = {"text": "x\n" * 999_000}
FLOOD_S = 8.0


def test_one_address_flooding_leaves_another_fast(tmp_path: Path) -> None:
    port = free_port()
    env = {
        "SEEBAND_API_PORT": str(port),
        "SEEBAND_API_CALC_PER_MINUTE": "1000000",
        "SEEBAND_API_PARSE_PER_MINUTE": "1000000",
    }
    command = [sys.executable, "-m", "seeband_api"]
    with running_server(command, port, tmp_path / "server.log", env) as client:
        # Workers start once before the clock runs.
        assert client.post("/api/calc", json=LIGHT).status_code == 200

        flooder_answers: list[tuple[int, float]] = []
        stop = threading.Event()

        def flood(body: dict[str, Any], path: str) -> None:
            with httpx2.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as flooder:
                while not stop.is_set():
                    started = time.perf_counter()
                    try:
                        response = flooder.post(
                            path, json=body, headers={"x-forwarded-for": "198.51.100.1"}
                        )
                    except httpx2.TransportError:
                        continue
                    flooder_answers.append((response.status_code, time.perf_counter() - started))

        loops = [threading.Thread(target=flood, args=(HEAVY, "/api/calc")) for _ in range(16)]
        loops += [
            threading.Thread(target=flood, args=(LARGEST_PARSE, "/api/parse")) for _ in range(4)
        ]
        for loop in loops:
            loop.start()
        latencies: list[float] = []
        statuses: list[int] = []
        try:
            time.sleep(0.5)
            deadline = time.monotonic() + FLOOD_S
            while time.monotonic() < deadline:
                started = time.perf_counter()
                response = client.post(
                    "/api/calc", json=LIGHT, headers={"x-forwarded-for": "203.0.113.2"}
                )
                latencies.append(time.perf_counter() - started)
                statuses.append(response.status_code)
                time.sleep(0.1)
        finally:
            stop.set()
            for loop in loops:
                loop.join(timeout=60)

    assert set(statuses) == {200}
    assert len(latencies) >= 20
    assert statistics.quantiles(latencies, n=20)[-1] < 1.0
    served = [took for status, took in flooder_answers if status == 200]
    refused = [took for status, took in flooder_answers if status in (429, 503)]
    assert served, "the flooder got nothing done"
    assert len(refused) > 100
    assert {status for status, _ in flooder_answers} <= {200, 429, 503}
    assert statistics.quantiles(refused, n=20)[-1] < 0.1
