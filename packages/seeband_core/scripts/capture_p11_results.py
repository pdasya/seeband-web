"""Capture P11 mixed-scattering regressions without replacing desktop or P8 evidence."""

import hashlib
import json
import platform
import runpy
import warnings
from pathlib import Path

import numpy as np
import scipy
from seeband_core import __version__ as CORE_VERSION

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "fixtures" / "physics" / "p11.json"
AFFECTED = {
    "dpb_see_res_fit",
    "dpb_see_res_hall_fit",
    "dpb_see_res_calc",
    "dpb_see_res_hall_calc",
    "dpb_see_with_scatter_calc",
}


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
            if scattering != "acPhDis" or call["function"] not in AFFECTED:
                continue
            key = replay["p8_key"](identifier, call)
            if call["function"].endswith("_fit"):
                fitted = replay["replay_fit"](mode, call)
                results[key] = {
                    "status": fitted.status,
                    "parameters": dict(fitted.parameters),
                    "iterations": fitted.iterations,
                    "message": fitted.message,
                }
            else:
                try:
                    result = replay["replay"](mode, scattering, call)
                except ValueError as error:
                    results[key] = {"error_type": type(error).__name__, "error": str(error)}
                else:
                    results[key] = {"result": serializable(result)}
    p8 = ROOT / "tests" / "fixtures" / "physics" / "p8.json"
    TARGET.write_text(
        json.dumps(
            {
                "description": (
                    "P11 implementation-generated regressions, not independent physics evidence."
                ),
                "core_version": CORE_VERSION,
                "p8_sha256": hashlib.sha256(p8.read_bytes()).hexdigest(),
                "affected_functions": sorted(AFFECTED),
                "environment": {
                    "python": platform.python_version(),
                    "numpy": np.__version__,
                    "scipy": scipy.__version__,
                    "platform": platform.platform(),
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
