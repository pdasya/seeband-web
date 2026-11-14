"""Capture P7 model-generated regression outputs; these are not independent physics evidence.

The original desktop interpolation_references.json remains unchanged. This script uses its
36 input cases, recording the clipped grid and values or the overlap failure for each.
Run from the repository root with the current seeband_core on PYTHONPATH.
"""

import hashlib
import json
import platform
from pathlib import Path

import numpy as np
from seeband_core.data_parser import parse_table
from seeband_core.interpolation import interpolate
from seeband_core.model_interface import Quantity

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def main() -> None:
    reference_path = FIXTURES / "interpolation_references.json"
    references = json.loads(reference_path.read_text("utf-8"))
    cases = []
    for original in references["cases"]:
        name = original["file"]
        kind: Quantity = {"see": "seebeck", "rho": "resistivity", "hall": "hall"}[
            Path(name).stem.rsplit("_", 1)[1]
        ]  # type: ignore[assignment]
        measurement = parse_table(
            (FIXTURES / "examples" / name).read_text("utf-8"), kind
        ).measurements[kind]
        case = {key: original[key] for key in ("file", "file_sha256", "min_k", "max_k")}
        try:
            result = interpolate(measurement, original["min_k"], original["max_k"])
        except ValueError as error:
            case["error"] = str(error)
        else:
            case.update(
                temperature_k=result.measurement.temperature_k.tolist(),
                values=result.measurement.values.tolist(),
                range_limited=result.range_limited,
                extrapolated=result.extrapolated,
                measured_points_in_range=result.measured_points_in_range,
                underdetermined=result.underdetermined,
            )
        cases.append(case)
    document = {
        "description": "P7 model-generated regression outputs, not independent physics evidence.",
        "desktop_reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "cases": cases,
    }
    (FIXTURES / "physics" / "p7.json").write_text(
        json.dumps(document, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
