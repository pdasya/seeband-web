"""Exact fit-local density reuse without changing the physical prediction budget."""

import numpy as np
import pytest
from seeband_core import math_module as mm
from seeband_core.band_models import DpbModel
from seeband_core.model_interface import Bounds, FitRequest, Measurement
from seeband_core.verified_fit import _CheckedRootProvider, _Engine, _evaluate_quantity


def test_scattering_predictions_reuse_checked_density(monkeypatch):
    t = np.linspace(100.0, 800.0, 4)
    p = dict(
        m_eff=1.2, band_gap=800.0, fermi_energy=-150.0, A=1e5, B=0.5, C=1.0, D=1.0, F=1e5, G=1.0
    )
    measurements = {
        q: Measurement(t, _evaluate_quantity(q, t, p, "dpb_s_rho", "acPh", 1.0))
        for q in ("seebeck", "resistivity")
    }
    request = FitRequest("dpb_s_rho", measurements, p, {"B": Bounds(0.0, 10.0)}, "acPh")
    engine = _Engine(request, DpbModel().describe().fit_mode(request.fit_mode))
    original = mm.dpb_chemPot_vs_temp
    calls = []

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(mm, "dpb_chemPot_vs_temp", counted)
    first = engine.predict("seebeck", p)
    second = engine.predict("resistivity", p | {"B": 2.0})
    assert len(calls) == 1
    assert engine.evaluations == 2
    np.testing.assert_array_equal(
        first, _evaluate_quantity("seebeck", t, p, request.fit_mode, "acPh", 1.0)
    )
    np.testing.assert_array_equal(
        second, _evaluate_quantity("resistivity", t, p | {"B": 2.0}, request.fit_mode, "acPh", 1.0)
    )


@pytest.mark.parametrize("model", ["spb", "dpb"])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("scattering", ["acPh", "dis"])
def test_cached_predictions_are_bitwise_identical(model, sign, scattering):
    t = np.array([100.0, 250.0, 800.0])
    p = dict(
        m_eff=sign * 3.6,
        band_gap=-500.0,
        fermi_energy=-165.0,
        band_mass=sign * 1.7,
        m1=1.2,
        A=1e5,
        B=2.0,
        C=2.0,
        D=0.5,
        F=1e5,
        G=2.0,
    )
    if model == "spb":
        p["fermi_energy"] = sign * 165.0
    provider = _CheckedRootProvider()
    for quantity in ("seebeck", "resistivity", "hall"):
        for changed in (p, p | {"B": 1.3, "G": 1.3, "A": 2e5, "C": 1.2}):
            expected = _evaluate_quantity(quantity, t, changed, model + "_s_rho_h", scattering, 3.0)
            actual = _evaluate_quantity(
                quantity, t, changed, model + "_s_rho_h", scattering, 3.0, root_provider=provider
            )
            assert actual.dtype == expected.dtype
            assert actual.tobytes() == expected.tobytes()
    if model == "dpb":
        # Seebeck-only has a distinct kernel but the same certified roots.
        expected = _evaluate_quantity("seebeck", t, p, "dpb_s", None, 3.0)
        actual = _evaluate_quantity("seebeck", t, p, "dpb_s", None, 3.0, root_provider=provider)
        assert actual.tobytes() == expected.tobytes()


def test_exact_root_keys_failures_isolation_and_bounds(monkeypatch):
    calls = []

    def roots(*args):
        calls.append(args)
        return np.arange(len(args[0]), dtype=float)

    monkeypatch.setattr(mm, "dpb_chemPot_vs_temp", roots)
    monkeypatch.setattr(mm, "spb_chemPot_vs_temp", roots)
    provider = _CheckedRootProvider()
    t = np.array([100.0, 200.0])
    args = ("dpb", t, 1.2, -150.0, -500.0, 3.0)
    first = provider(*args)
    first[:] = -999.0
    assert provider(*args).tolist() == [0.0, 1.0]
    assert len(calls) == 1
    variants = [
        ("dpb", t[::-1], 1.2, -150.0, -500.0, 3.0),
        ("dpb", t.astype(np.float32), 1.2, -150.0, -500.0, 3.0),
        ("dpb", t + 1.0, 1.2, -150.0, -500.0, 3.0),
        ("dpb", t, -1.2, -150.0, -500.0, 3.0),
        ("dpb", t, np.float64(1.2), -150.0, -500.0, 3.0),
        ("dpb", t, 1.2, -151.0, -500.0, 3.0),
        ("dpb", t, 1.2, -150.0, -501.0, 3.0),
        ("dpb", t, 1.2, -150.0, -500.0, 2.0),
        ("spb", t, 1.2, -150.0),
        ("dpb", t, 1.2, -150.0, 0.0, 3.0),
        ("dpb", t, 1.2, -150.0, -0.0, 3.0),
    ]
    for variant in variants:
        provider(*variant)
        provider(*variant)
    assert len(calls) == 1 + len(variants)
    t[0] = 101.0
    provider(*args)
    assert len(calls) == 2 + len(variants)
    # A fresh fit cannot observe a previous fit's cached roots.
    _CheckedRootProvider()(*args)
    assert len(calls) == 3 + len(variants)
    for ef in range(40):
        provider("dpb", t, 1.2, float(ef), -500.0, 3.0)
    before = len(calls)
    provider("dpb", t, 1.2, 0.0, -500.0, 3.0)
    assert len(calls) == before + 1  # oldest entry was evicted
    large = np.arange(10001, dtype=float)
    provider("dpb", large, 1.2, -150.0, -500.0, 3.0)
    provider("dpb", large, 1.2, -150.0, -500.0, 3.0)
    assert len(calls) == before + 3

    def failed(*args):
        calls.append(args)
        raise mm.ChemicalPotentialError(100.0, "uncertified", 1.0)

    monkeypatch.setattr(mm, "dpb_chemPot_vs_temp", failed)
    for _ in range(2):
        with pytest.raises(mm.ChemicalPotentialError):
            provider("dpb", t, 1.2, -999.0, -500.0, 3.0)
    assert len(calls) == before + 5


def test_bounded_stage_retains_endpoint_and_counters(monkeypatch):
    t = np.linspace(100.0, 800.0, 4)
    p = dict(
        m_eff=1.2, band_gap=800.0, fermi_energy=-150.0, A=1e5, B=0.5, C=1.0, D=1.0, F=1e5, G=1.0
    )
    measurements = {
        q: Measurement(t, _evaluate_quantity(q, t, p | {"B": 2.0}, "dpb_s_rho", "acPh", 1.0))
        for q in ("seebeck", "resistivity")
    }
    request = FitRequest(
        "dpb_s_rho",
        measurements,
        p,
        {"B": Bounds(0.0, 10.0)},
        "acPh",
        held=frozenset({"m_eff", "band_gap", "fermi_energy"}),
    )
    mode = DpbModel().describe().fit_mode(request.fit_mode)
    cached, direct = _Engine(request, mode), _Engine(request, mode)
    direct._root_provider = None
    endpoint, stationarity = cached.stage("resistivity", p)
    expected, expected_stationarity = direct.stage("resistivity", p)
    assert endpoint == expected
    assert stationarity == expected_stationarity
    assert cached.evaluations == direct.evaluations
    cached.values = endpoint
    direct.values = expected

    def forbidden(*args):
        raise AssertionError("Terminal audit must bypass root reuse")

    monkeypatch.setattr(_CheckedRootProvider, "__call__", forbidden)
    result = cached.result("converged", "test", True)
    expected_result = direct.result("converged", "test", True)
    assert result == expected_result


def test_complete_fit_retains_status_endpoint_and_counters(monkeypatch):
    t = np.linspace(100.0, 800.0, 4)
    p = dict(
        m_eff=1.2, band_gap=800.0, fermi_energy=-150.0, A=1e5, B=0.5, C=1.0, D=1.0, F=1e5, G=1.0
    )
    measurements = {
        q: Measurement(t, _evaluate_quantity(q, t, p | {"B": 2.0}, "dpb_s_rho", "acPh", 1.0))
        for q in ("seebeck", "resistivity")
    }
    request = FitRequest(
        "dpb_s_rho",
        measurements,
        p,
        {"B": Bounds(0.0, 10.0)},
        "acPh",
        held=frozenset({"m_eff", "band_gap", "fermi_energy"}),
    )
    cached = DpbModel().fit(request)
    original = _CheckedRootProvider.__call__

    def uncached(self, *args):
        return original(_CheckedRootProvider(), *args)

    monkeypatch.setattr(_CheckedRootProvider, "__call__", uncached)
    direct = DpbModel().fit(request)
    assert cached == direct
    assert cached.status == "converged"
