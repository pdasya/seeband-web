"""Capture P4/P12 Hall curves and explicitly synthetic six-case fit evidence.

Original desktop fixtures remain unchanged. Run with the current core on PYTHONPATH.
"""

import json
import platform
import runpy
from pathlib import Path

import numpy as np
import scipy
from seeband_core.model_catalog import registry
from seeband_core.model_interface import Bounds, CurveRequest, FitRequest, Measurement
from seeband_core.model_scales import default_start

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "tests" / "fixtures" / "physics" / "p4.json"


def main() -> None:
    replay = runpy.run_path(str(ROOT / "tests" / "test_golden_regression.py"))
    desktop = {}
    for identifier, (_example, mode, scattering, _source, call) in zip(
        replay["CALL_IDS"], replay["CALLS"], strict=True
    ):
        if call["function"] == "spb_see_res_hall_calc" and "error" not in call:
            desktop[identifier] = replay["replay"](mode, scattering, call)[-1].tolist()

    synthetic = {}
    model = registry.get("spb")
    mode = model.describe().fit_mode("spb_s_rho_rh")
    for mass in [-1.5, 1.5]:
        for scattering in ["acPh", "dis", "acPhDis"]:
            known = default_start(mode) | {
                "band_mass": mass,
                "fermi_energy": np.sign(mass) * 250.0,
                "A": 3000.0,
                "C": 0.7,
                "F": 2.0,
            }
            curve = model.calculate(CurveRequest(mode.id, known, 100, 800, 12, scattering))
            measurements = {
                quantity: Measurement(curve.temperature_k, curve.curves[column])
                for quantity, column in [
                    ("seebeck", "seebeck_v_per_k"),
                    ("resistivity", "resistivity_ohm_m"),
                    ("hall", "hall_m3_per_c"),
                ]
            }
            start = known | {
                "band_mass": mass * 0.8,
                "fermi_energy": known["fermi_energy"] * 0.7,
                "A": 2500.0,
                "C": 0.4,
                "F": 1.5,
            }
            bounds = Bounds(0.5, 2.5) if mass > 0 else Bounds(-2.5, -0.5)
            result = model.fit(
                FitRequest(mode.id, measurements, start, {"band_mass": bounds}, scattering)
            )
            if result.status != "converged":
                raise RuntimeError(f"Synthetic fit failed: {mass}, {scattering}: {result.message}")
            synthetic[f"{mass}:{scattering}"] = {
                "known_parameters": known,
                "start": start,
                "mass_bounds": [bounds.lower, bounds.upper],
                "fit_status": result.status,
                "fitted_parameters": result.parameters,
                "temperature_k": curve.temperature_k.tolist(),
                "curves": {name: values.tolist() for name, values in curve.curves.items()},
            }
    TARGET.write_text(
        json.dumps(
            {
                "provenance": "Synthetic exact-model data, not experimental validation. "
                "Human physicist confirmation remains pending before release.",
                "environment": {
                    "python": platform.python_version(),
                    "numpy": np.__version__,
                    "scipy": scipy.__version__,
                },
                "desktop_hall_curves": desktop,
                "synthetic": synthetic,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
