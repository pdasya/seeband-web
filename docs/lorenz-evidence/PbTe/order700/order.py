# ruff: noqa: T201 -- print replay results for reviewers.
"""Report fixed-density PbTe decomposition and source contrasts at 700 K."""

from pathlib import Path

import numpy as np
import pandas as pd

out = Path(__file__).resolve().parent
calc = pd.read_csv(out.parent / "seeband.csv").query('scenario == "density" and T_K == 700').copy()
ref = pd.read_csv(out.parent / "reference.csv")
for style in ("solid", "dotted"):
    measured = []
    for p in calc.p20:
        curve = ref[(ref.p_cm3 == p * 1e20) & (ref["style"] == style)].sort_values("temperature_k")
        assert curve.temperature_k.min() < 700 < curve.temperature_k.max()
        measured.append(np.interp(700, curve.temperature_k, curve.lorenz_1e8_w_ohm_k2))
    calc["ref_" + style] = measured
calc["ref_mixing"] = calc.ref_solid - calc.ref_dotted
calc["model_mixing"] = calc.hole_hole + calc.bipolar
assert np.allclose(calc.total, calc.intraband + calc.model_mixing)
calc.to_csv(out / "budget-700K.csv", index=False)
keys = ["intraband", "hole_hole", "bipolar", "total", "ref_dotted", "ref_mixing", "ref_solid"]
print(calc[["p20", *keys]].round(5).to_string(index=False))
print("High minus low", (calc.iloc[-1][keys] - calc.iloc[0][keys]).to_dict())
