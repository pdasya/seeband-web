"""Capture synthetic P6 DPB S non-unit-degeneracy references; keep desktop goldens intact."""

import json
from pathlib import Path

from seeband_core.fit_module import PB_fit

TARGET = Path(__file__).parents[1] / "tests" / "fixtures" / "physics" / "p6.json"


def main():
    cases = []
    parameters = [1.2, 800.0, -150.0]
    start = [1.15, 780.0, -140.0]
    bounds = ([0.8, 600.0, -250.0], [1.8, 1000.0, -50.0])
    for degeneracy in (3.0, 0.5, 1.5):
        temperature, measured = PB_fit().dpb_see_calc(100, 800, 20, parameters, degeneracy)
        fitted = PB_fit().dpb_see_fit(temperature, measured, start, bounds, degeneracy)
        _, redrawn = PB_fit().dpb_see_calc(100, 800, 20, fitted, degeneracy)
        cases.append(
            {
                "degeneracy_ratio": degeneracy,
                "parameters": parameters,
                "start": start,
                "bounds": bounds,
                "temperature_k": temperature.tolist(),
                "seebeck_v_per_k": measured.tolist(),
                "fitted_parameters": fitted,
                "redrawn_seebeck_v_per_k": redrawn.tolist(),
            }
        )
    TARGET.write_text(json.dumps({"synthetic": True, "cases": cases}, indent=1) + "\n")


if __name__ == "__main__":
    main()
