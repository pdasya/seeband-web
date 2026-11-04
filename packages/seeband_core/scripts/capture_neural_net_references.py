"""Capture neural net reference outputs from the SeeBand desktop code.

Needs a SeeBand checkout and an environment with TensorFlow, h5py and numpy. It is not part
of the normal setup. See docs/neural-net-references.md for the command and versions.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

MODEL_RANGES = [(300, 800), (400, 700), (300, 600), (200, 500), (100, 400)]
EXAMPLES = ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]
MASS_SLIDER_RANGE = (-300, 300)
ENERGY_SLIDER_RANGE = (-3000, 3000)


def clamp(value: int, limits: tuple[int, int]) -> int:
    return max(limits[0], min(limits[1], value))


def capture_case(models: Any, np: Any, name: str, kind: str, data: Any) -> dict[str, Any]:
    """Follow Models.get_prediction step by step and record each intermediate value."""
    temperature_k, seebeck_v_per_k = data[:, 0], data[:, 1]
    case: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "temperature_k": [float(x) for x in temperature_k],
        "seebeck_v_per_k": [float(x) for x in seebeck_v_per_k],
    }
    models._select_model(temperature_k)
    if models.current_model is None:
        if models.get_prediction(temperature_k, seebeck_v_per_k) is not None:
            raise RuntimeError(f"{name}: get_prediction returned a value with no model")
        case["selected_range_k"] = None
        return case

    interpolated = models._interpolate_seebeck(temperature_k, seebeck_v_per_k)
    transformed = models._transform_seebeck(interpolated)
    raw = models.current_model.predict(transformed.reshape(1, -1), verbose=0)[0]
    reversed_norm = models._reverse_norm(raw)
    prediction = models._transform_prediction(interpolated, reversed_norm)
    direct = models.get_prediction(temperature_k, seebeck_v_per_k)
    if not np.allclose(np.array(direct, dtype=float), np.array(prediction, dtype=float)):
        raise RuntimeError(f"{name}: steps do not reproduce get_prediction")

    # The slider conversions and Qt clamping from NeuralNetPredictionThread, seeband.py:5083-5085.
    mass_slider = clamp(int(np.round(prediction[0] * 100)), MASS_SLIDER_RANGE)
    gap_slider = clamp(round(prediction[1]), ENERGY_SLIDER_RANGE)
    fermi_slider = clamp(round(prediction[2]), ENERGY_SLIDER_RANGE)
    case |= {
        "selected_range_k": [models.t_min, models.t_max],
        "interpolated_seebeck_v_per_k": [float(x) for x in interpolated],
        "network_input": [float(x) for x in transformed],
        "network_output": [float(x) for x in raw],
        "reversed_norm": [float(x) for x in reversed_norm],
        "prediction": [float(x) for x in prediction],
        "desktop_start_values": {
            "m_eff": mass_slider / 100.0,
            "band_gap_k": gap_slider,
            "fermi_energy_k": fermi_slider,
        },
    }
    return case


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desktop", type=Path, required=True, help="SeeBand checkout")
    parser.add_argument("--output", type=Path, required=True, help="JSON file to write")
    args = parser.parse_args()
    output = args.output.resolve()
    desktop = args.desktop.resolve()

    sys.dont_write_bytecode = True
    sys.path.insert(0, str(desktop))
    os.chdir(desktop)

    import h5py
    import keras
    import numpy as np
    import tensorflow as tf
    from modules import data_processing as dp
    from modules import neural_nets as nn

    models = nn.Models()
    cases = []
    for example in EXAMPLES:
        data = dp.get_data(f"data/Examples/{example}_see.txt")
        cases.append(capture_case(models, np, example, "example", data))

    first = dp.get_data(f"data/Examples/{EXAMPLES[0]}_see.txt")
    cases.append(capture_case(models, np, "01_reversed_rows", "derived", first[::-1]))
    last = dp.get_data(f"data/Examples/{EXAMPLES[2]}_see.txt")
    negated = np.column_stack((last[:, 0], -last[:, 1]))
    cases.append(capture_case(models, np, "03_negated_seebeck", "derived", negated))

    # Examples do not select every network, so synthetic data covers the rest.
    for low, high in MODEL_RANGES:
        temperature_k = np.linspace(low, high, 30)
        seebeck = 20e-6 + 0.2e-6 * temperature_k
        name = f"synthetic_{low}_{high}"
        data = np.column_stack((temperature_k, seebeck))
        cases.append(capture_case(models, np, name, "synthetic", data))

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    weights = sorted(Path("Models").glob("*"))
    document = {
        "description": "Outputs of the SeeBand desktop neural nets, for checking the numpy port.",
        "source": {"repository": "https://github.com/xAngelswordx/SeeBand", "commit": commit},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "tensorflow": tf.__version__,
            "keras": keras.__version__,
            "numpy": np.__version__,
            "h5py": h5py.__version__,
        },
        "model_files_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in weights
        },
        "cases": cases,
    }
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
