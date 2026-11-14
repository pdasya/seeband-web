"""Synthetic evidence for #80; run with the checkout's seeband_core on PYTHONPATH."""

import json
import platform
import subprocess
import warnings

import numpy as np
from seeband_core import math_module as math


def main() -> None:
    results: dict[str, object] = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform": platform.platform(),
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "data": "synthetic; energies in K, Seebeck in microvolt/K",
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        alone = math.dpb_see_vs_temp_double_scatter(
            np.array([300.0]), 1.0, 300.0, -100.0, 1.0, 1.0, 150.0, 600.0
        )
        grid = np.array([300.0, 800.0])
        total = math.dpb_see_vs_temp_double_scatter(
            grid, 1.0, 300.0, -100.0, 1.0, 1.0, 150.0, 600.0
        )
        bands = math.dpb_indCont_see_vs_temp_double_scatter(
            grid, 1.0, 300.0, -100.0, 1.0, 1.0, 150.0, 600.0
        )
        results["P11_102"] = {
            "S_300_alone": float(alone[0] * 1e6),
            "S_300_on_grid": float(total[0] * 1e6),
            "S_300_sum_of_bands": float((bands[0][0] + bands[1][0]) * 1e6),
        }
        results["P14_105"] = {
            "F0_minus40_actual": math.fdint_robust(0, -40.0, 1.0),
            "F0_minus40_reference": float(np.logaddexp(0.0, -40.0)),
        }
        results["P16_107"] = {
            "S_300_EF100": float(
                math.dpb_see_vs_temp(np.array([300.0]), 1.0, 600.0, 100.0, 1.0)[0] * 1e6
            ),
            "S_300_EF500": float(
                math.dpb_see_vs_temp(np.array([300.0]), 1.0, 600.0, 500.0, 1.0)[0] * 1e6
            ),
        }
        results["P8_87"] = {
            "mu_at_EF_zero": float(
                math.dpb_chemPot_vs_temp(np.array([50.0]), 1000.0, 1.01, 0.0, 1.0)[0]
            ),
            "mu_at_EF_minus_1e_minus6": float(
                math.dpb_chemPot_vs_temp(np.array([50.0]), 1000.0, 1.01, -1e-6, 1.0)[0]
            ),
        }
        results["warnings"] = sorted({str(w.message) for w in caught})
    print(json.dumps(results, indent=2, allow_nan=False))  # noqa: T201


if __name__ == "__main__":
    main()
