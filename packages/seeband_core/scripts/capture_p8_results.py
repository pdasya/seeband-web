"""Capture P8 regression results from the historical inputs, not independent physics evidence.

Original desktop recordings stay unchanged. Every call is recorded, including failed fits and
explicit chemical-potential errors, so a failure cannot silently disappear from the comparison.
"""

import hashlib
import json
import platform
import runpy
import warnings
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "fixtures" / "physics" / "p8.json"


def serializable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, tuple | list):
        return [serializable(part) for part in value]
    return value


def main():
    replay = runpy.run_path(str(ROOT / "tests" / "test_golden_regression.py"))
    results = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for identifier, (_, mode, scattering, _, call) in zip(
            replay["CALL_IDS"], replay["CALLS"], strict=True
        ):
            identifier = replay["p8_key"](identifier, call)
            if call["function"].endswith("_fit"):
                fitted = replay["replay_fit"](mode, call)
                results[identifier] = {
                    "status": fitted.status,
                    "parameters": dict(fitted.parameters),
                    "iterations": fitted.iterations,
                    "message": fitted.message,
                }
            else:
                try:
                    result = replay["replay"](mode, scattering, call)
                except ValueError as error:
                    results[identifier] = {"error_type": type(error).__name__, "error": str(error)}
                else:
                    results[identifier] = {"result": serializable(result)}
    sources = ROOT / "tests" / "fixtures" / "golden"
    TARGET.write_text(
        json.dumps(
            {
                "description": (
                    "P8 implementation-generated regression outputs; "
                    "not independent physics evidence."
                ),
                "environment": {
                    "python": platform.python_version(),
                    "numpy": np.__version__,
                    "scipy": scipy.__version__,
                    "platform": platform.platform(),
                },
                "desktop_sha256": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(sources.glob("*.json"))
                },
                "results": results,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
