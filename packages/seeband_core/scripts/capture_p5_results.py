"""Capture P5 fits and iteration evidence, leaving desktop recordings unchanged."""

import json
import platform
import runpy
from pathlib import Path

import numpy as np
import scipy
from seeband_core.fit_module import FitProgress

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "tests" / "fixtures" / "physics" / "p5.json"


def main():
    replay = runpy.run_path(str(ROOT / "tests" / "test_golden_regression.py"))
    results = {}
    for identifier, (_example, _mode, scattering, _source, call) in zip(
        replay["CALL_IDS"], replay["CALLS"], strict=True
    ):
        if scattering != "acPhDis" or call["function"] not in {
            "dpb_see_res_fit",
            "dpb_see_res_hall_fit",
        }:
            continue
        if "error" in call:
            continue
        args, kwargs = replay["core_arguments"](call["function"], call["args"], call["kwargs"])
        history = []
        progress = FitProgress(on_iteration=lambda i, p, history=history: history.append([i, p]))
        result = getattr(replay["fit_module"].PB_fit(), call["function"])(
            *args, **kwargs, progress=progress
        )
        results[identifier] = {
            "result": [float(value) for value in result],
            "iterations": progress.iterations,
            "reached_iteration_limit": progress.reached_iteration_limit,
            "history": history,
        }
    TARGET.write_text(
        json.dumps(
            {
                "environment": {
                    "python": platform.python_version(),
                    "numpy": np.__version__,
                    "scipy": scipy.__version__,
                    "platform": platform.platform(),
                },
                "results": results,
            },
            indent=1,
            allow_nan=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
