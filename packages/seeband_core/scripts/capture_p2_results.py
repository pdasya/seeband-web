"""Capture P2 expectations using the original desktop inputs; preserve desktop fixtures."""

import json
import runpy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "tests" / "fixtures" / "physics" / "p2.json"


def serialise(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [serialise(item) for item in value]
    return value


def main():
    replay = runpy.run_path(str(ROOT / "tests" / "test_golden_regression.py"))
    results = {}
    for identifier, (_example, mode, scattering, _source, call) in zip(
        replay["CALL_IDS"], replay["CALLS"], strict=True
    ):
        if call["function"] not in {"dpb_see_res_hall_calc", "dpb_see_res_hall_fit"}:
            continue
        if "error" in call:
            continue
        if identifier in results:
            raise ValueError(f"Duplicate reference: {identifier}")
        results[identifier] = serialise(replay["replay"](mode, scattering, call))
    TARGET.parent.mkdir(exist_ok=True)
    TARGET.write_text(json.dumps(results, indent=1, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
