"""Capture aggregate verified-fit evidence without replacing historical fixtures.

Run from the repository environment. These are generated numerical observations,
not independent physical targets or portable parameter goldens.
"""

import dataclasses
import hashlib
import json
import platform
import runpy
from pathlib import Path

import numpy as np
import scipy
from seeband_core import __version__ as CORE_VERSION
from seeband_core.model_catalog import registry

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "fixtures" / "physics" / "p19.json"
CASES = {
    "01_Fe2VAl09Si01-d1-dis-thread-dpb_see_res_hall_fit",
    "02_SiP-dpb_s_rho-acPhDis-thread-dpb_see_res_fit",
    "03_AWI32_SI-dpb_s_rho-acPhDis-thread-dpb_see_res_fit",
}


def main() -> None:
    replay = runpy.run_path(str(ROOT / "tests" / "test_golden_regression.py"))
    results = {}
    for identifier, (_, mode, _, _, call) in zip(replay["CALL_IDS"], replay["CALLS"], strict=True):
        if identifier not in CASES:
            continue
        if "-d1-" in identifier:
            mode = "dpb_s_rho_rh"
        request = dataclasses.replace(
            replay["fit_request"](mode, call), algorithm="verified-sequential-v2"
        )
        result = registry.get("dpb").fit(request)
        results[identifier] = dataclasses.asdict(result)
    if set(results) != CASES:
        raise ValueError("A recorded P19 evidence case is missing")
    TARGET.write_text(
        json.dumps(
            {
                "description": (
                    "P19 implementation-generated aggregate observations; not physical "
                    "acceptance targets or portable parameter goldens."
                ),
                "core_version": CORE_VERSION,
                "prior_sha256": {
                    name: hashlib.sha256(
                        (ROOT / "tests" / "fixtures" / "physics" / name).read_bytes()
                    ).hexdigest()
                    for name in ("p8.json", "p11.json", "p13.json")
                },
                "environment": {
                    "python": platform.python_version(),
                    "numpy": np.__version__,
                    "scipy": scipy.__version__,
                    "platform": platform.platform(),
                },
                "results": results,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
