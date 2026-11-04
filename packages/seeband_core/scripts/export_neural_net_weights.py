"""Export the SeeBand neural net weights to one .npz file per net.

Needs a clean SeeBand checkout, and an environment with h5py and numpy. It is not part of the
normal setup. See docs/neural-net-references.md for the command and versions.
"""

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import h5py
import numpy as np

DESKTOP_COMMIT = "803b0e7a425a0a3f4f59688df77e3ad283ca49a1"
NET_NAMES = ["100_400", "200_500", "300_600", "300_800", "400_700"]
INPUT_SIZE = 7
DENSE_UNITS = [16, 16, 8, 3]
LEAKY_RELU_ALPHA = 0.10000000149011612


def check_checkout(desktop: Path) -> None:
    def git(*args: str) -> str:
        command = ["git", "-C", str(desktop), *args]
        return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()

    if git("rev-parse", "HEAD") != DESKTOP_COMMIT:
        raise SystemExit(f"SeeBand must be at commit {DESKTOP_COMMIT}")
    if git("status", "--porcelain"):
        raise SystemExit("SeeBand has local changes")


def dense_layer_names(architecture: dict[str, Any]) -> list[str]:
    """Return the Dense layers in order, and stop if a net is not the expected shape."""
    layers = architecture["config"]["layers"]
    kinds = [layer["class_name"] for layer in layers]
    expected = ["InputLayer", "Dense", "LeakyReLU", "Dense", "LeakyReLU", "Dense", "LeakyReLU"]
    if kinds != [*expected, "Dense"]:
        raise SystemExit(f"Unexpected layers: {kinds}")
    dense = [layer["config"] for layer in layers if layer["class_name"] == "Dense"]
    if [config["units"] for config in dense] != DENSE_UNITS:
        raise SystemExit("Unexpected layer sizes")
    if [config["activation"] for config in dense] != ["linear", "linear", "linear", "tanh"]:
        raise SystemExit("Unexpected activations")
    if layers[0]["config"]["batch_input_shape"] != [None, INPUT_SIZE]:
        raise SystemExit("Unexpected input size")
    alphas = {layer["config"]["alpha"] for layer in layers if layer["class_name"] == "LeakyReLU"}
    if alphas != {LEAKY_RELU_ALPHA}:
        raise SystemExit(f"Unexpected LeakyReLU slope: {alphas}")
    return [config["name"] for config in dense]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desktop", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    check_checkout(arguments.desktop)

    arguments.output.mkdir(parents=True, exist_ok=True)
    for name in NET_NAMES:
        models = arguments.desktop / "Models"
        text = (models / f"model_{name}_architecture.json").read_text(encoding="utf-8")
        arrays = {}
        with h5py.File(models / f"model_{name}_weights.h5", "r") as weights:
            for index, layer in enumerate(dense_layer_names(json.loads(text))):
                arrays[f"kernel_{index}"] = np.array(weights[layer][layer]["kernel:0"])
                arrays[f"bias_{index}"] = np.array(weights[layer][layer]["bias:0"])
        np.savez(arguments.output / f"net_{name}.npz", **arrays)


if __name__ == "__main__":
    main()
