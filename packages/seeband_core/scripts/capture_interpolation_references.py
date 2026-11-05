"""Capture interpolated data from the SeeBand desktop code, for the numpy of the golden results.

Needs a clean SeeBand checkout and an environment with numpy. It is not part of the normal setup.
See docs/interpolation.md for the command and versions.
"""

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

DESKTOP_COMMIT = "803b0e7a425a0a3f4f59688df77e3ad283ca49a1"
RANGES_K = [(50, 800), (100, 500), (300, 700), (5, 240)]


def main() -> None:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desktop", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    def git(*args: str) -> str:
        command = ["git", "-C", str(arguments.desktop), *args]
        return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()

    if git("rev-parse", "HEAD") != DESKTOP_COMMIT or git("status", "--porcelain"):
        raise SystemExit(f"SeeBand must be clean at commit {DESKTOP_COMMIT}")

    path = arguments.desktop / "modules" / "data_processing.py"
    spec = importlib.util.spec_from_file_location("desktop_data_processing", path)
    assert spec is not None and spec.loader is not None
    desktop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(desktop)

    cases = []
    for example in sorted((arguments.desktop / "data" / "Examples").glob("*.txt")):
        data = desktop.get_data(str(example))
        for low_k, high_k in RANGES_K:
            # The expression of int_seeb_data_button_clicked, seeband.py:3380.
            grid = np.linspace(low_k, high_k, int((high_k - low_k) / 20.0))
            values = desktop.interpolate_data(desktop.fit_data(data, 10), grid)
            cases.append(
                {
                    "file": example.name,
                    "file_sha256": hashlib.sha256(example.read_bytes()).hexdigest(),
                    "min_k": low_k,
                    "max_k": high_k,
                    "temperature_k": [float(value) for value in values[:, 0]],
                    "values": [float(value) for value in values[:, 1]],
                }
            )
    document = {
        "description": "Interpolated data from the SeeBand desktop code, at the commit below.",
        "source": {"repository": "xAngelswordx/SeeBand", "commit": DESKTOP_COMMIT},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "cases": cases,
    }
    arguments.output.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
