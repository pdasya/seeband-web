"""Terminal fit diagnostics independently solve roots despite enclosing curve reuse."""

import numpy as np
import pytest
from seeband_core import math_module as mm
from seeband_core import verified_fit
from seeband_core.band_models import SpbModel
from seeband_core.model_interface import FitRequest, Measurement


@pytest.mark.parametrize("scattering", ["acPh", "ionized"])
def test_terminal_audit_solves_fresh_and_restores_prediction_reuse(monkeypatch, scattering):
    t = np.array([100.0, 300.0, 500.0])
    p = {"band_mass": -1.0, "fermi_energy": -165.0}
    request = FitRequest(
        "spb_s",
        {"seebeck": Measurement(t, np.zeros(3))},
        p,
        scattering=scattering,
        held=frozenset({"fermi_energy"}),
    )
    engine = verified_fit._Engine(request, SpbModel().describe().fit_mode("spb_s"))
    solve = mm._solve_chemical_potential
    calls = 0
    fail = False

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if fail:
            raise RuntimeError("synthetic audit failure")
        return solve(*args, **kwargs)

    monkeypatch.setattr(mm, "_solve_chemical_potential", counted)
    with mm.reuse_chemical_potential():
        engine.predict("seebeck", p)
        engine.predict("seebeck", p)
        assert calls == 1
        engine.result("converged", "conditional_stage_optima", True)
        assert calls == 2
        engine.predict("seebeck", p)
        mm.spb_chemPot_vs_temp(t, p["band_mass"], p["fermi_energy"])
        assert calls == 2
        fail = True
        with pytest.raises(RuntimeError, match="synthetic audit failure"):
            engine.result("converged", "conditional_stage_optima", True)
        fail = False
        mm.spb_chemPot_vs_temp(t, p["band_mass"], p["fermi_energy"])
        assert calls == 3
    assert mm._REUSED_ROOTS.get() is None
