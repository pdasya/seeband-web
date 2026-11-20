"""Capture P14 model replay and synthetic SPB Hall regressions."""

import hashlib
import json
import platform
import runpy
import warnings
from pathlib import Path

import numpy as np
import scipy
from capture_p8_results import serializable
from seeband_core import __version__ as CORE_VERSION
from seeband_core.model_catalog import registry
from seeband_core.model_interface import Bounds, CurveRequest, FitRequest, Measurement

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TARGET = FIXTURES / "physics" / "p14.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_hall() -> dict:
    earlier = json.loads((FIXTURES / "physics" / "p4.json").read_text())["synthetic"]
    model = registry.get("spb")
    mode = "spb_s_rho_rh"
    results = {}
    for key, reference in earlier.items():
        _, scattering = key.split(":")
        if scattering not in {"acPh", "dis"}:
            continue
        known = reference["known_parameters"]
        mass = known["band_mass"]
        curve = model.calculate(CurveRequest(mode, known, 100, 800, 12, scattering))
        measurements = {
            quantity: Measurement(curve.temperature_k.copy(), curve.curves[column].copy())
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
        mass_bounds = Bounds(0.5, 2.5) if mass > 0 else Bounds(-2.5, -0.5)
        fitted = model.fit(
            FitRequest(mode, measurements, start, {"band_mass": mass_bounds}, scattering)
        )
        assert fitted.status == "converged", fitted.message
        results[key] = {
            "known_parameters": known,
            "fitted_parameters": dict(fitted.parameters),
            "curves": {column: values.tolist() for column, values in curve.curves.items()},
        }
    return results


def main() -> None:
    replay = runpy.run_path(str(ROOT / "tests" / "test_golden_regression.py"))
    results = {}
    functions = set()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for identifier, (_, mode, scattering, _, call) in zip(
            replay["CALL_IDS"], replay["CALLS"], strict=True
        ):
            function = call["function"]
            if not replay["affected_by_p14"](scattering, call):
                continue
            key = replay["p8_key"](identifier, call)
            functions.add(function)
            if function.endswith("_fit"):
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
    TARGET.write_text(
        json.dumps(
            {
                "description": (
                    "P14 implementation-generated model replay and synthetic SPB Hall regressions."
                ),
                "core_version": CORE_VERSION,
                "environment": {
                    "python": platform.python_version(),
                    "numpy": np.__version__,
                    "scipy": scipy.__version__,
                    "platform": platform.platform(),
                },
                "desktop_sha256": {
                    path.name: sha256(path) for path in sorted((FIXTURES / "golden").glob("*.json"))
                },
                "prior_sha256": {
                    name: sha256(FIXTURES / "physics" / name)
                    for name in replay["P14_PRIOR_FIXTURES"]
                },
                "affected_functions": sorted(functions),
                "results": results,
                "synthetic": synthetic_hall(),
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
