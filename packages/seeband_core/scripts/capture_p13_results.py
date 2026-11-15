"""Capture branch-constrained DPB fit regressions; preserve earlier evidence."""

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
TARGET = ROOT / "tests" / "fixtures" / "physics" / "p13.json"
AFFECTED = {"dpb_see_fit", "dpb_see_res_fit", "dpb_see_res_hall_fit"}


def main():
    replay = runpy.run_path(str(ROOT / "tests" / "test_golden_regression.py"))
    results = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for identifier, (_, mode, _, _, call) in zip(
            replay["CALL_IDS"], replay["CALLS"], strict=True
        ):
            if call["function"] not in AFFECTED:
                continue
            fitted = replay["replay_fit"](mode, call)
            results[replay["p8_key"](identifier, call)] = {
                "status": fitted.status,
                "parameters": dict(fitted.parameters),
                "iterations": fitted.iterations,
                "message": fitted.message,
            }
    TARGET.write_text(
        json.dumps(
            {
                "description": (
                    "P13 implementation-generated fit regressions, not independent physics "
                    "evidence. Initial mass sign fixes the optimization branch."
                ),
                "core_version": CORE_VERSION,
                "prior_sha256": {
                    name: hashlib.sha256(
                        (ROOT / "tests" / "fixtures" / "physics" / name).read_bytes()
                    ).hexdigest()
                    for name in ("p8.json", "p11.json")
                },
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
