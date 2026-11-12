import copy
import dataclasses
import json
import math
import subprocess
import sys
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import ANY

import numpy as np
import pytest
from scipy import optimize as opt
from seeband_core import band_models, fit_module
from seeband_core import math_module as te
from seeband_core.band_models import parabolic_band
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    BandDiagramRequest,
    BandDiagramResult,
    Bounds,
    CurveKind,
    CurveRequest,
    FitMode,
    FitRequest,
    FitStopped,
    IterationUpdate,
    Measurement,
    Quantity,
)
from seeband_core.model_scales import default_start

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
CURVE_NAMES: dict[CurveKind, list[str]] = {
    "seebeck": ["seebeck_v_per_k"],
    "seebeck_by_band": ["seebeck_band_1_v_per_k", "seebeck_band_2_v_per_k"],
    "chemical_potential": ["chemical_potential_k"],
    "electrical_conductivity": ["electrical_conductivity_s_per_m"],
    "electrical_conductivity_by_band": [
        "electrical_conductivity_band_1_s_per_m",
        "electrical_conductivity_band_2_s_per_m",
    ],
    "thermal_conductivity": ["thermal_conductivity_w_per_m_k"],
    "carrier_concentration_by_band": [
        "carrier_concentration_band_1_per_cm3",
        "carrier_concentration_band_2_per_cm3",
    ],
}
MEASURED_NAMES = {
    "seebeck": "seebeck_v_per_k",
    "resistivity": "resistivity_ohm_m",
    "hall": "hall_m3_per_c",
}


def fit_modes() -> list[tuple[str, FitMode]]:
    return [
        (description.id, fit_mode)
        for description in registry.descriptions()
        for fit_mode in description.fit_modes
    ]


def combinations() -> list[tuple[str, str, str | None]]:
    found: list[tuple[str, str, str | None]] = []
    for model_id, fit_mode in fit_modes():
        options: tuple[str | None, ...] = fit_mode.scattering or (None,)
        found += [(model_id, fit_mode.id, scattering) for scattering in options]
    return found


def curve_cases() -> list[tuple[str, str, str | None, CurveKind]]:
    cases: list[tuple[str, str, str | None, CurveKind]] = []
    for model_id, fit_mode_id, scattering in combinations():
        kinds = registry.get(model_id).describe().fit_mode(fit_mode_id).curve_kinds
        cases += [(model_id, fit_mode_id, scattering, kind) for kind in kinds]
    return cases


def recorded_measurements(fit_mode: FitMode) -> dict[Quantity, Measurement]:
    document = json.loads((GOLDEN / "03_AWI32_SI.json").read_text(encoding="utf-8"))
    calls = (call for run in document["runs"] for call in run["calls"])
    args = next(c for c in calls if c["function"] == "dpb_see_res_hall_fit" and "error" not in c)[
        "args"
    ]
    arrays = [np.array(value) for value in args[:6]]
    all_data: dict[Quantity, Measurement] = {
        "seebeck": Measurement(arrays[0], arrays[1]),
        "resistivity": Measurement(arrays[2], arrays[3]),
        "hall": Measurement(arrays[4], arrays[5]),
    }
    return {quantity: all_data[quantity] for quantity in fit_mode.quantities}


def test_both_models_are_registered_in_order() -> None:
    assert [description.id for description in registry.descriptions()] == ["spb", "dpb"]


def test_a_new_process_gets_the_models_from_its_imports(tmp_path: Path) -> None:
    code = (
        "from seeband_core.model_catalog import registry;"
        "print([item.id for item in registry.descriptions()])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "['spb', 'dpb']"


def test_every_combination_is_covered() -> None:
    assert len(combinations()) == 14


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering", "kind"), curve_cases())
def test_every_curve_runs(
    model_id: str, fit_mode_id: str, scattering: str | None, kind: CurveKind
) -> None:
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    result = model.calculate(
        CurveRequest(fit_mode_id, default_start(fit_mode), 50, 800, 5, scattering, kind)
    )
    assert result.temperature_k.tolist() == np.linspace(50, 800, 5).tolist()
    expected = (
        [MEASURED_NAMES[quantity] for quantity in fit_mode.quantities]
        if kind == "measured"
        else CURVE_NAMES[kind]
    )
    assert list(result.curves) == expected
    for curve in result.curves.values():
        assert len(curve) == 5


WORKING_FITS = [case for case in combinations() if case[1] != "spb_s_rho_rh"]


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering"), WORKING_FITS)
def test_every_working_fit_returns_all_parameters_and_keeps_its_request(
    model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    measurements = recorded_measurements(fit_mode)
    start = default_start(fit_mode)
    start_before = copy.deepcopy(start)
    values_before = {name: data.values.copy() for name, data in measurements.items()}

    result = model.fit(FitRequest(fit_mode_id, measurements, start, scattering=scattering))

    assert result.status == "converged"
    assert set(result.parameters) == set(start)
    assert start == start_before
    for name, data in measurements.items():
        assert np.array_equal(data.values, values_before[name])
    for spec in fit_mode.parameters:
        if spec.role == "fixed":
            assert result.parameters[spec.name] == start[spec.name]


STAGE_QUANTITIES = {"see": "seebeck", "res": "resistivity", "hall": "hall"}


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering"), WORKING_FITS)
def test_a_fit_runs_the_stages_of_its_description_in_their_order(
    monkeypatch: pytest.MonkeyPatch, model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    run: list[str] = []
    real = fit_module._curve_fit

    def recording(progress: Any, stage: str, *args: Any, **kwargs: Any) -> Any:
        run.append(STAGE_QUANTITIES[stage])
        return real(progress, stage, *args, **kwargs)

    monkeypatch.setattr(fit_module, "_curve_fit", recording)
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    result = model.fit(
        FitRequest(
            fit_mode_id,
            recorded_measurements(fit_mode),
            default_start(fit_mode),
            scattering=scattering,
        )
    )

    stages = fit_mode.stages
    first_runs = list(dict.fromkeys(run))
    assert first_runs == [stage.quantity for stage in stages]
    for stage in stages:
        if stage.repeats:
            assert run.count(stage.quantity) >= (result.iterations or 1)
        else:
            assert run.count(stage.quantity) == 1


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering"), WORKING_FITS)
def test_each_stage_finds_the_parameters_of_its_description(
    monkeypatch: pytest.MonkeyPatch, model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    results: dict[str, Any] = {}
    real = fit_module._curve_fit

    def recording(progress: Any, stage: str, *args: Any, **kwargs: Any) -> Any:
        result = real(progress, stage, *args, **kwargs)
        results[stage] = result
        return result

    monkeypatch.setattr(fit_module, "_curve_fit", recording)
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    model.fit(
        FitRequest(
            fit_mode_id,
            recorded_measurements(fit_mode),
            default_start(fit_mode),
            scattering=scattering,
        )
    )
    fitted = {spec.name for spec in fit_mode.parameters_for(scattering) if spec.role == "fitted"}
    quantities = {quantity: stage for stage, quantity in STAGE_QUANTITIES.items()}
    for stage in fit_mode.stages:
        values = results[quantities[stage.quantity]][0]
        # One stage at a time, with errors of 1, through the model's own naming of its runs.
        one = fit_module.FitProgress(
            stage_fits={quantities[stage.quantity]: (values, np.eye(len(values)))}
        )
        named = model._stage_errors(fit_mode, scattering, 1.0, one)  # type: ignore[attr-defined]
        assert set(named) == set(stage.parameters) & fitted, (fit_mode_id, scattering, stage)


def test_stages_cover_the_quantities_and_find_parameters_of_the_mode() -> None:
    for description in registry.descriptions():
        for fit_mode in description.fit_modes:
            names = {spec.name for spec in fit_mode.parameters}
            assert tuple(stage.quantity for stage in fit_mode.stages) == fit_mode.quantities
            for stage in fit_mode.stages:
                assert set(stage.parameters) <= names, (fit_mode.id, stage)
                assert not stage.repeats or fit_mode.iterative
            fitted = {spec.name for spec in fit_mode.parameters if spec.role == "fitted"}
            found = {name for stage in fit_mode.stages for name in stage.parameters}
            assert fitted <= found, fit_mode.id


@pytest.mark.filterwarnings("ignore")
def test_inactive_parameters_come_back_unchanged() -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho")
    start = default_start(fit_mode)
    result = model.fit(
        FitRequest("dpb_s_rho", recorded_measurements(fit_mode), start, scattering="acPh")
    )
    for name in ("C", "D", "F", "G"):
        assert result.parameters[name] == start[name]


@pytest.mark.filterwarnings("ignore")
def test_web_bounds_of_d1_let_the_fit_run_and_desktop_bounds_fail_as_recorded() -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho_rh")
    measurements = recorded_measurements(fit_mode)
    start = default_start(fit_mode)
    result = model.fit(FitRequest("dpb_s_rho_rh", measurements, start, scattering="dis"))
    assert result.status == "converged"
    assert 0.5 <= result.parameters["G"] <= 2
    failed = model.fit(
        FitRequest(
            "dpb_s_rho_rh",
            measurements,
            start,
            bounds={"G": Bounds(50, 200)},
            scattering="dis",
        )
    )
    assert failed.status == "failed"
    assert failed.message == "The start values do not fit the bounds."
    assert failed.parameters == start


@pytest.mark.filterwarnings("ignore")
def test_request_bounds_override_only_what_they_name() -> None:
    model = registry.get("spb")
    fit_mode = model.describe().fit_mode("spb_s")
    start = default_start(fit_mode)
    result = model.fit(
        FitRequest(
            "spb_s",
            recorded_measurements(fit_mode),
            start,
            bounds={"fermi_energy": Bounds(100, 110)},
        )
    )
    assert 100 <= result.parameters["fermi_energy"] <= 110


@pytest.mark.filterwarnings("ignore")
def test_the_spb_hall_fit_keeps_its_recorded_problems() -> None:
    model = registry.get("spb")
    fit_mode = model.describe().fit_mode("spb_s_rho_rh")
    measurements = recorded_measurements(fit_mode)
    start = default_start(fit_mode)
    # D3: a positive mass gives an empty start for E.
    empty = model.fit(FitRequest("spb_s_rho_rh", measurements, start, scattering="acPh"))
    assert (empty.status, empty.message) == ("failed", "The start values do not fit the bounds.")
    float_mass = model.fit(
        FitRequest("spb_s_rho_rh", measurements, start | {"band_mass": -1.5}, scattering="acPh")
    )
    assert (float_mass.status, float_mass.message) == (
        "failed",
        "The fit failed with an internal error.",
    )
    result = model.fit(
        FitRequest(
            "spb_s_rho_rh",
            measurements,
            start | {"band_mass": -1, "fermi_energy": -100},
            bounds={"band_mass": Bounds(0, 10)},
            scattering="acPh",
        )
    )
    assert result.status == "converged"
    assert set(result.parameters) == set(start)


def test_degeneracy_is_the_ratio_of_the_two_bands() -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    start = default_start(fit_mode)
    ratio = model.calculate(CurveRequest("dpb_s", start, 100, 300, 3, band_2_degeneracy=2.0))
    both = model.calculate(
        CurveRequest("dpb_s", start, 100, 300, 3, band_1_degeneracy=2.0, band_2_degeneracy=4.0)
    )
    base = model.calculate(CurveRequest("dpb_s", start, 100, 300, 3))
    assert np.array_equal(ratio.curves["seebeck_v_per_k"], both.curves["seebeck_v_per_k"])
    assert not np.array_equal(ratio.curves["seebeck_v_per_k"], base.curves["seebeck_v_per_k"])


@pytest.mark.parametrize(
    ("model_id", "request_", "error", "message"),
    [
        ("dpb", CurveRequest("dpb_s_rho", {}, 50, 800, 5), ValueError, "needs a scattering"),
        ("dpb", CurveRequest("dpb_s", {}, 50, 800, 5, "acPh"), ValueError, "no scattering type"),
        ("dpb", CurveRequest("nothing", {}, 50, 800, 5), KeyError, "no fit mode"),
        ("dpb", CurveRequest("dpb_s", {}, 50, 800, 5), ValueError, "Missing parameters"),
        (
            "dpb",
            CurveRequest("dpb_s", {}, 50, 800, 5, kind="thermal_conductivity"),
            ValueError,
            "no curve thermal_conductivity",
        ),
        (
            "spb",
            CurveRequest("spb_s", {}, 50, 800, 5, kind="seebeck_by_band"),
            ValueError,
            "no curve seebeck_by_band",
        ),
    ],
)
def test_invalid_curve_requests_are_errors(
    model_id: str, request_: CurveRequest, error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        registry.get(model_id).calculate(request_)


def test_a_fit_needs_its_measurements() -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s_rho")
    only_seebeck = {"seebeck": recorded_measurements(fit_mode)["seebeck"]}
    with pytest.raises(ValueError, match="Missing measurement: resistivity"):
        model.fit(FitRequest("dpb_s_rho", only_seebeck, default_start(fit_mode), scattering="acPh"))


def _golden_runs() -> Iterator[tuple[str, dict[str, Any]]]:
    for path in sorted(GOLDEN.glob("*.json")):
        for run in json.loads(path.read_text(encoding="utf-8"))["runs"]:
            yield path.stem, run


def _band_calls(run: dict[str, Any]) -> list[dict[str, Any]]:
    return [call for call in run["manual_curve_calls"] if call["function"] == "get_parabolic_band"]


def _diagram_of(run: dict[str, Any]) -> tuple[BandDiagramResult, list[dict[str, Any]]]:
    """The diagram for the values of a run's recorded calls, with those calls."""
    mode_id = run["mode"]
    model = registry.get(mode_id.partition("_")[0])
    fit_mode = model.describe().fit_mode(mode_id)
    band, fermi = _band_calls(run)
    mass, energy = band["args"][3:5]
    parameters = {
        **default_start(fit_mode),
        "fermi_energy": fermi["args"][4],
    }
    if model.describe().id == "spb":
        parameters["band_mass"] = mass
    else:
        parameters |= {"m_eff": mass, "band_gap": energy}
    return model.band_diagram(BandDiagramRequest(mode_id, parameters)), [band, fermi]


def test_the_diagram_is_what_the_desktop_draws() -> None:
    compared = 0
    for _, run in _golden_runs():
        if not _band_calls(run) or run["mode"] == "spb_s_rho_rh":
            continue
        result, (band, fermi) = _diagram_of(run)
        name = "band_1_energy_k" if run["mode"].startswith("spb") else "band_2_energy_k"
        assert result.wavevector.tolist() == band["result"][0]
        assert result.curves[name].tolist() == band["result"][1]
        assert result.curves["fermi_energy_k"].tolist() == fermi["result"][1]
        compared += 1
    assert compared > 10


def test_the_diagram_scales_band_2_as_the_desktop_does() -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    result = registry.get("dpb").band_diagram(
        BandDiagramRequest(
            "dpb_s",
            {**default_start(fit_mode), "m_eff": 1.5, "band_gap": 700.0},
            band_1_degeneracy=2.0,
            band_2_degeneracy=3.0,
        )
    )

    # As `seeband.py:3585`: the mass over N1/N2.
    expected = parabolic_band(-40, 40, 100, 1.5 / (2 / 3), 700.0)[1]
    assert result.curves["band_2_energy_k"].tolist() == expected.tolist()
    assert result.curves["band_1_energy_k"].tolist() == (
        parabolic_band(-40, 40, 100, -1, 0)[1].tolist()
    )


def test_the_diagram_shows_a_mass_as_the_user_sees_it() -> None:
    # This disabled mode holds its mass 100 times larger in core units (D3).
    fit_mode = registry.get("spb").describe().fit_mode("spb_s_rho_rh")
    result = registry.get("spb").band_diagram(
        BandDiagramRequest("spb_s_rho_rh", {**default_start(fit_mode), "band_mass": 150.0})
    )

    expected = parabolic_band(-40, 40, 100, 1.5, 0)[1]
    assert result.curves["band_1_energy_k"].tolist() == expected.tolist()


def test_the_diagram_lists_its_own_known_error() -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    result = registry.get("dpb").band_diagram(BandDiagramRequest("dpb_s", default_start(fit_mode)))
    assert result.known_issues == ("band_diagram_formula",)


def test_a_mass_of_0_has_no_finite_band_and_no_warning() -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = registry.get("dpb").band_diagram(
            BandDiagramRequest("dpb_s", {**default_start(fit_mode), "m_eff": 0.0})
        )
    assert not np.isfinite(result.curves["band_2_energy_k"]).any()
    assert np.isfinite(result.curves["band_1_energy_k"]).all()


@pytest.mark.parametrize("m_eff", [1e-310, 1e300, -1e-310])
def test_extreme_masses_give_no_warning(m_eff: float) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = registry.get("dpb").band_diagram(
            BandDiagramRequest("dpb_s", {**default_start(fit_mode), "m_eff": m_eff})
        )
    assert np.isfinite(result.curves["fermi_energy_k"]).all()


def test_band_diagram_is_available_without_a_model() -> None:
    wavevector, energy = parabolic_band(-1.0, 1.0, 3, 1.0, 5.0)
    assert wavevector.tolist() == [-1.0, 0.0, 1.0]
    assert energy[1] == 5.0


# Distinct values, so that a swapped argument shows.
PARAMETERS: dict[str, float] = {
    "band_mass": 11.5,
    "m_eff": 1.25,
    "band_gap": 2.5,
    "fermi_energy": 3.5,
    "A": 4.5,
    "B": 5.5,
    "C": 6.5,
    "D": 7.5,
    "F": 8.5,
    "G": 9.5,
    "m1": 10.5,
}
BANDS = [1.25, 2.5, 3.5]
DPB_RES = [4.5, 5.5, 6.5, 7.5, 8.5, 9.5]
SPB_RES = [4.5, 6.5, 8.5]
RATIO = 1.5  # Band 2 degeneracy of 3 over band 1 degeneracy of 2.
GRID = [50, 800, 5]

# (mode, kind): the core function, and its arguments after the grid. S is the scattering type.
S = "scattering"
EXPECTED_CURVE_CALLS: dict[tuple[str, str], tuple[str, list[Any], list[str]]] = {
    ("spb_s", "measured"): ("spb_see_calc", [11.5, 3.5], ["seebeck_v_per_k"]),
    ("spb_s", "chemical_potential"): ("spb_chemPot_calc", [11.5, 3.5], ["chemical_potential_k"]),
    ("spb_s_rho", "measured"): (
        "spb_see_res_calc",
        [11.5, 3.5, SPB_RES, S],
        ["seebeck_v_per_k", "resistivity_ohm_m"],
    ),
    ("spb_s_rho", "chemical_potential"): (
        "spb_chemPot_calc",
        [11.5, 3.5],
        ["chemical_potential_k"],
    ),
    ("spb_s_rho", "electrical_conductivity"): (
        "spb_elecCond_calc",
        [11.5, 3.5, SPB_RES, S],
        ["electrical_conductivity_s_per_m"],
    ),
    ("spb_s_rho", "thermal_conductivity"): (
        "spb_thermCond_calc",
        [11.5, 3.5, SPB_RES, S],
        ["thermal_conductivity_w_per_m_k"],
    ),
    ("spb_s_rho_rh", "measured"): (
        "spb_see_res_hall_calc",
        [11.5, 3.5, SPB_RES, S],
        ["seebeck_v_per_k", "resistivity_ohm_m", "hall_m3_per_c"],
    ),
    ("spb_s_rho_rh", "chemical_potential"): (
        "spb_chemPot_calc",
        [11.5, 3.5],
        ["chemical_potential_k"],
    ),
    ("spb_s_rho_rh", "electrical_conductivity"): (
        "spb_elecCond_calc",
        [11.5, 3.5, SPB_RES, S],
        ["electrical_conductivity_s_per_m"],
    ),
    ("spb_s_rho_rh", "thermal_conductivity"): (
        "spb_thermCond_calc",
        [11.5, 3.5, SPB_RES, S],
        ["thermal_conductivity_w_per_m_k"],
    ),
    ("dpb_s", "measured"): ("dpb_see_calc", [BANDS, RATIO], ["seebeck_v_per_k"]),
    ("dpb_s", "seebeck_by_band"): (
        "dpb_ind_see_seeOnly_calc",
        [BANDS, RATIO],
        ["seebeck_band_1_v_per_k", "seebeck_band_2_v_per_k"],
    ),
    ("dpb_s", "chemical_potential"): (
        "dpb_chemPot_calc",
        [BANDS, RATIO],
        ["chemical_potential_k"],
    ),
    ("dpb_s", "carrier_concentration_by_band"): (
        "dpb_ind_carCon_calc",
        [BANDS, RATIO],
        ["carrier_concentration_band_1_per_cm3", "carrier_concentration_band_2_per_cm3"],
    ),
}
for _mode, _hall in (("dpb_s_rho", False), ("dpb_s_rho_rh", True)):
    EXPECTED_CURVE_CALLS |= {
        (_mode, "measured"): (
            "dpb_see_res_hall_calc" if _hall else "dpb_see_res_calc",
            [BANDS, DPB_RES, 10.5, RATIO, S] if _hall else [BANDS, DPB_RES, RATIO, S],
            [
                "seebeck_v_per_k",
                "resistivity_ohm_m",
                *(["hall_m3_per_c"] if _hall else []),
            ],
        ),
        (_mode, "seebeck"): (
            "dpb_see_with_scatter_calc",
            [BANDS, DPB_RES, RATIO, S],
            ["seebeck_v_per_k"],
        ),
        (_mode, "seebeck_by_band"): (
            "dpb_ind_see_calc",
            [BANDS, DPB_RES, RATIO, S],
            ["seebeck_band_1_v_per_k", "seebeck_band_2_v_per_k"],
        ),
        (_mode, "chemical_potential"): (
            "dpb_chemPot_calc",
            [BANDS, RATIO],
            ["chemical_potential_k"],
        ),
        (_mode, "electrical_conductivity"): (
            "dpb_elecCond_calc",
            [BANDS, DPB_RES, RATIO, S],
            ["electrical_conductivity_s_per_m"],
        ),
        (_mode, "electrical_conductivity_by_band"): (
            "dpb_ind_elecCond_calc",
            [BANDS, DPB_RES, RATIO, S],
            ["electrical_conductivity_band_1_s_per_m", "electrical_conductivity_band_2_s_per_m"],
        ),
        (_mode, "thermal_conductivity"): (
            "dpb_thermCond_calc",
            [BANDS, DPB_RES, RATIO, S],
            ["thermal_conductivity_w_per_m_k"],
        ),
        (_mode, "carrier_concentration_by_band"): (
            "dpb_ind_carCon_calc_m1" if _hall else "dpb_ind_carCon_calc",
            [BANDS, RATIO, 10.5] if _hall else [BANDS, RATIO],
            ["carrier_concentration_band_1_per_cm3", "carrier_concentration_band_2_per_cm3"],
        ),
    }

# Each parameter's bounds are distinct too: lower is minus its value, upper is 100 plus its value.
BOUNDS = {name: Bounds(-value, 100 + value) for name, value in PARAMETERS.items()}


def limits(*names: str) -> list[list[float]]:
    return [[BOUNDS[name].lower for name in names], [BOUNDS[name].upper for name in names]]


BAND_NAMES = ("m_eff", "band_gap", "fermi_energy")
DPB_NAMES = ("A", "B", "C", "D", "F", "G")
SPB_NAMES = ("A", "C", "F")
DATA_S = ["T_S", "S"]
DATA_R = ["T_R", "R"]
DATA_H = ["T_H", "H"]
# mode: the core function, its positional arguments, its keyword arguments, and the name of each
# value it returns, in order.
EXPECTED_FIT_CALLS: dict[str, tuple[str, list[Any], dict[str, Any], list[str]]] = {
    "spb_s": (
        "spb_see_fit",
        [*DATA_S, 11.5, [3.5], limits("fermi_energy")],
        {"progress": ANY},
        ["fermi_energy"],
    ),
    "spb_s_rho": (
        "spb_see_res_fit",
        [*DATA_S, *DATA_R, 11.5, [3.5], limits("fermi_energy"), SPB_RES, limits(*SPB_NAMES)],
        {"scatter_type": S, "progress": ANY},
        ["fermi_energy", "A", "C", "F"],
    ),
    "spb_s_rho_rh": (
        "spb_see_res_hall_fit",
        [
            *DATA_S,
            *DATA_R,
            *DATA_H,
            [3.5],
            limits("fermi_energy"),
            SPB_RES,
            limits(*SPB_NAMES),
            [11.5],
            limits("band_mass"),
            S,
        ],
        {"progress": ANY},
        ["fermi_energy", "A", "C", "F", "band_mass"],
    ),
    "dpb_s": (
        "dpb_see_fit",
        [*DATA_S, BANDS, limits(*BAND_NAMES), RATIO],
        {"progress": ANY},
        ["m_eff", "band_gap", "fermi_energy"],
    ),
    "dpb_s_rho": (
        "dpb_see_res_fit",
        [
            *DATA_S,
            *DATA_R,
            BANDS,
            limits(*BAND_NAMES),
            DPB_RES,
            limits(*DPB_NAMES),
            RATIO,
            S,
            0.1,
            1000,
        ],
        {"progress": ANY},
        ["m_eff", "band_gap", "fermi_energy", "A", "B", "C", "D", "F", "G"],
    ),
    "dpb_s_rho_rh": (
        "dpb_see_res_hall_fit",
        [
            *DATA_S,
            *DATA_R,
            *DATA_H,
            BANDS,
            limits(*BAND_NAMES),
            DPB_RES,
            limits(*DPB_NAMES),
            10.5,
            limits("m1"),
            RATIO,
            S,
            0.1,
            20,
        ],
        {"progress": ANY},
        ["m_eff", "band_gap", "fermi_energy", "A", "B", "C", "D", "F", "G", "m1"],
    ),
}


class RecordingCore:
    """Stands in for the core, records the one call it gets, and returns numbered values."""

    def __init__(self, returned: Any) -> None:
        self.returned = returned
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args, kwargs))
            return self.returned

        return record


def request_values(fit_mode: FitMode) -> dict[str, float]:
    return {spec.name: PARAMETERS[spec.name] for spec in fit_mode.parameters}


def with_scattering(values: list[Any], scattering: str | None) -> list[Any]:
    return [scattering if value is S else value for value in values]


def test_the_expected_tables_cover_every_mode_and_kind() -> None:
    assert {(mode, kind) for _, mode, _, kind in curve_cases()} == set(EXPECTED_CURVE_CALLS)
    assert {mode for _, mode, _ in combinations()} == set(EXPECTED_FIT_CALLS)


@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering", "kind"), curve_cases())
def test_curves_call_the_core_as_written_here(
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
    fit_mode_id: str,
    scattering: str | None,
    kind: CurveKind,
) -> None:
    function, arguments, names = EXPECTED_CURVE_CALLS[(fit_mode_id, kind)]
    returned = ("temperature", *[f"curve {index}" for index in range(len(names))])
    core = RecordingCore(returned)
    monkeypatch.setattr(band_models, "_CORE", core)
    model = registry.get(model_id)
    result = model.calculate(
        CurveRequest(
            fit_mode_id,
            request_values(model.describe().fit_mode(fit_mode_id)),
            *GRID,  # type: ignore[arg-type]
            scattering=scattering,
            kind=kind,
            band_1_degeneracy=2.0,
            band_2_degeneracy=3.0,
        )
    )
    assert core.calls == [(function, (*GRID, *with_scattering(arguments, scattering)), {})]
    assert result.temperature_k == "temperature"
    assert result.curves == {name: f"curve {index}" for index, name in enumerate(names)}


@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering"), combinations())
def test_fits_call_the_core_as_written_here(
    monkeypatch: pytest.MonkeyPatch, model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    function, arguments, keywords, names = EXPECTED_FIT_CALLS[fit_mode_id]
    core = RecordingCore([100.0 + index for index in range(len(names))])
    monkeypatch.setattr(band_models, "_CORE", core)
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    start = request_values(fit_mode)
    arrays = {name: np.array([1.0, 2.0]) for name in ("T_S", "S", "T_R", "R", "T_H", "H")}
    names_of_arrays = {id(array): name for name, array in arrays.items()}
    all_data: dict[Quantity, Measurement] = {
        "seebeck": Measurement(arrays["T_S"], arrays["S"]),
        "resistivity": Measurement(arrays["T_R"], arrays["R"]),
        "hall": Measurement(arrays["T_H"], arrays["H"]),
    }
    bounds = {
        spec.name: BOUNDS[spec.name] for spec in fit_mode.parameters if spec.fit_bounds is not None
    }
    result = model.fit(
        FitRequest(
            fit_mode_id,
            {quantity: all_data[quantity] for quantity in fit_mode.quantities},
            start,
            bounds,
            scattering,
            band_1_degeneracy=2.0,
            band_2_degeneracy=3.0,
        )
    )
    expected_keywords = {
        key: scattering if value is S else value for key, value in keywords.items()
    }
    called, positional, called_keywords = core.calls[0]
    named_positional = tuple(names_of_arrays.get(id(value), value) for value in positional)
    assert (called, named_positional, called_keywords) == (
        function,
        tuple(with_scattering(arguments, scattering)),
        expected_keywords,
    )
    assert len(core.calls) == 1
    fitted = {name: 100.0 + index for index, name in enumerate(names)}
    assert result.parameters == start | fitted


@pytest.mark.parametrize("fit_mode_id", list(EXPECTED_FIT_CALLS))
def test_a_fit_returning_the_wrong_length_is_an_error(
    monkeypatch: pytest.MonkeyPatch, fit_mode_id: str
) -> None:
    names = EXPECTED_FIT_CALLS[fit_mode_id][3]
    monkeypatch.setattr(band_models, "_CORE", RecordingCore([0.0] * (len(names) + 1)))
    model = registry.get(fit_mode_id.partition("_")[0])
    fit_mode = model.describe().fit_mode(fit_mode_id)
    data = {quantity: Measurement(np.ones(1), np.ones(1)) for quantity in fit_mode.quantities}
    with pytest.raises(ValueError, match="zip"):
        model.fit(
            FitRequest(
                fit_mode_id,
                data,
                request_values(fit_mode),
                scattering=fit_mode.default_scattering,
            ),
        )


def test_a_curve_returning_the_wrong_length_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(band_models, "_CORE", RecordingCore(("t", "a", "b")))
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    with pytest.raises(ValueError, match="zip"):
        model.calculate(
            CurveRequest("dpb_s", request_values(fit_mode), 50, 800, 5, kind="chemical_potential")
        )


@pytest.mark.parametrize(("first", "second"), [(0.0, 1.0), (1.0, 0.0), (-1.0, 1.0)])
def test_degeneracies_must_be_positive(first: float, second: float) -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    values = default_start(fit_mode)
    with pytest.raises(ValueError, match="must be positive"):
        model.calculate(
            CurveRequest(
                "dpb_s", values, 50, 800, 5, band_1_degeneracy=first, band_2_degeneracy=second
            )
        )
    with pytest.raises(ValueError, match="must be positive"):
        model.fit(
            FitRequest(
                "dpb_s",
                recorded_measurements(fit_mode),
                values,
                band_1_degeneracy=first,
                band_2_degeneracy=second,
            )
        )


@pytest.mark.parametrize(
    ("bounds", "start_extra", "message"),
    [
        ({"Fermi_energy": Bounds(0, 1)}, {}, "does not fit a parameter Fermi_energy"),
        ({"band_mass": Bounds(5, 6)}, {}, "does not fit a parameter band_mass"),
        ({}, {"nonsense": 1.0}, "has no parameters"),
    ],
)
def test_names_a_fit_cannot_use_are_errors(
    bounds: dict[str, Bounds], start_extra: dict[str, float], message: str
) -> None:
    model = registry.get("spb")
    fit_mode = model.describe().fit_mode("spb_s")
    with pytest.raises(ValueError, match=message):
        model.fit(
            FitRequest(
                "spb_s",
                recorded_measurements(fit_mode),
                default_start(fit_mode) | start_extra,
                bounds,
            )
        )


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("model_id", "fit_mode_id"), [("spb", "spb_s_rho"), ("dpb", "dpb_s_rho")])
@pytest.mark.parametrize("scattering", ["acPh", "dis"])
def test_curve_names_mean_what_they_say(model_id: str, fit_mode_id: str, scattering: str) -> None:
    model = registry.get(model_id)
    values = default_start(model.describe().fit_mode(fit_mode_id))
    if model_id == "spb":
        values |= {"band_mass": -1.0, "fermi_energy": -500.0}
    else:
        values |= {"band_gap": 2000.0, "fermi_energy": -500.0}

    def curves(kind: CurveKind) -> dict[str, np.ndarray]:
        return dict(
            model.calculate(CurveRequest(fit_mode_id, values, 100, 300, 3, scattering, kind)).curves
        )

    measured = curves("measured")
    conductivity = curves("electrical_conductivity")["electrical_conductivity_s_per_m"]
    thermal = curves("thermal_conductivity")["thermal_conductivity_w_per_m_k"]
    # Conductivity is the inverse of resistivity with these scattering types.
    assert conductivity * measured["resistivity_ohm_m"] == pytest.approx(1.0)
    # kappa / (sigma T) is a Lorenz number, here between its limits of about 1.5e-8 and 2.44e-8.
    lorenz = thermal / (conductivity * np.array([100.0, 200.0, 300.0]))
    assert np.all((lorenz > 1.4e-8) & (lorenz < 2.5e-8))
    # A valence band with a Fermi energy inside it gives a positive Seebeck coefficient of µV/K.
    assert np.all(np.abs(measured["seebeck_v_per_k"]) < 1e-3)
    assert np.all(measured["seebeck_v_per_k"] > 0)


def recorded_fit_calls() -> list[tuple[str, dict[str, Any]]]:
    found = []
    for name in ("01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"):
        document = json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8"))
        for run in document["runs"]:
            for call in run["calls"]:
                if call["function"].endswith("_fit"):
                    found.append((run["mode"], call))
    return found


def recorded_limits(call: dict[str, Any]) -> list[tuple[str, list[list[float]]]]:
    args = call["args"]
    match call["function"]:
        case "spb_see_fit":
            return [("fermi_energy", args[4])]
        case "spb_see_res_fit":
            return [("fermi_energy", args[6]), ("res", args[8])]
        case "dpb_see_fit":
            return [("bands", args[3])]
        case "dpb_see_res_fit":
            return [("bands", args[5]), ("res", args[7])]
        case _:
            return [("bands", args[7]), ("res", args[9]), ("m1", args[11])]


GROUPS = {
    "fermi_energy": ("fermi_energy",),
    "bands": ("m_eff", "band_gap", "fermi_energy"),
    "m1": ("m1",),
}


@pytest.mark.parametrize(("mode", "call"), recorded_fit_calls())
def test_described_bounds_match_what_the_desktop_passed(mode: str, call: dict[str, Any]) -> None:
    fit_mode = registry.get(mode.partition("_")[0]).describe().fit_mode(mode)
    specs = {spec.name: spec for spec in fit_mode.parameters}
    for group, limits in recorded_limits(call):
        if group == "res":
            names = ("A", "C", "F") if mode.startswith("spb") else ("A", "B", "C", "D", "F", "G")
        else:
            names = GROUPS[group]
        for name, lower, upper in zip(names, limits[0], limits[1], strict=True):
            bounds = specs[name].fit_bounds
            assert bounds is not None
            if mode == "dpb_s_rho_rh" and name == "G":
                assert (lower, upper) == (50, 200)
                assert bounds == Bounds(0.5, 2)
            else:
                assert (bounds.lower, bounds.upper) == (lower, upper)


ITERATIVE_CASES = [
    ("dpb_s_rho", "acPh"),
    ("dpb_s_rho", "dis"),
    ("dpb_s_rho", "acPhDis"),
    ("dpb_s_rho_rh", "acPh"),
    ("dpb_s_rho_rh", "dis"),
    ("dpb_s_rho_rh", "acPhDis"),
]


def iterative_request(fit_mode_id: str, scattering: str, degeneracy: float = 1.0) -> FitRequest:
    fit_mode = registry.get("dpb").describe().fit_mode(fit_mode_id)
    return FitRequest(
        fit_mode_id,
        recorded_measurements(fit_mode),
        default_start(fit_mode),
        scattering=scattering,
        band_2_degeneracy=degeneracy,
    )


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("fit_mode_id", "scattering"), ITERATIVE_CASES)
def test_a_callback_changes_no_number_and_follows_each_iteration(
    fit_mode_id: str, scattering: str
) -> None:
    model = registry.get("dpb")
    request = iterative_request(fit_mode_id, scattering, degeneracy=2.0)
    plain = model.fit(request)
    updates: list[IterationUpdate] = []
    followed = model.fit(request, updates.append)

    assert followed.parameters == plain.parameters
    assert plain.status == followed.status == "converged"
    assert plain.iterations == followed.iterations
    assert [update.iteration for update in updates] == list(range(1, len(updates) + 1))
    assert len(updates) == followed.iterations
    # The last update has the form of the result, including its conversions, apart from m1.
    fitted_later = {"m1"} if fit_mode_id == "dpb_s_rho_rh" else set()
    for name, value in updates[-1].parameters.items():
        if name not in fitted_later:
            assert value == followed.parameters[name], name
    assert all(update.parameters["m1"] == 1.0 for update in updates if fitted_later)
    assert len({id(update.parameters) for update in updates}) == len(updates)


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("fit_mode_id", "scattering"), ITERATIVE_CASES)
def test_a_callback_can_stop_a_fit(fit_mode_id: str, scattering: str) -> None:
    updates: list[IterationUpdate] = []

    def stop(update: IterationUpdate) -> None:
        updates.append(update)
        raise FitStopped

    result = registry.get("dpb").fit(iterative_request(fit_mode_id, scattering), stop)
    assert result.status == "stopped"
    assert result.iterations == 1
    assert result.parameters == updates[-1].parameters
    assert len(updates) == 1


def model_with_loop(fit_mode_id: str, threshold: float, limit: int) -> band_models.DpbModel:
    model = band_models.DpbModel()
    description = model.describe()
    modes = tuple(
        dataclasses.replace(mode, threshold=threshold, max_iterations=limit)
        if mode.id == fit_mode_id
        else mode
        for mode in description.fit_modes
    )
    model._description = dataclasses.replace(description, fit_modes=modes)
    return model


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("fit_mode_id", "scattering"), ITERATIVE_CASES)
@pytest.mark.parametrize("with_callback", [True, False])
def test_reaching_the_iteration_limit_is_not_success(
    fit_mode_id: str, scattering: str, with_callback: bool
) -> None:
    model = model_with_loop(fit_mode_id, 1e-300, 2)
    updates: list[IterationUpdate] = []
    result = model.fit(
        iterative_request(fit_mode_id, scattering), updates.append if with_callback else None
    )
    assert result.status == "iteration_limit"
    assert result.iterations == 2
    if with_callback:
        assert [update.iteration for update in updates] == [1, 2]
        # The result has a Seebeck fit from the extra iteration, and the resistivity of the last.
        last = updates[-1].parameters
        for name in ("A", "B", "C", "D", "F", "G"):
            assert result.parameters[name] == last[name]
        assert result.parameters["band_gap"] != last["band_gap"]


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("fit_mode_id", "scattering"), ITERATIVE_CASES)
def test_converging_on_the_last_allowed_iteration_is_success(
    fit_mode_id: str, scattering: str
) -> None:
    request = iterative_request(fit_mode_id, scattering)
    natural = registry.get("dpb").fit(request)
    assert natural.iterations is not None
    threshold = registry.get("dpb").describe().fit_mode(fit_mode_id).threshold
    assert threshold is not None
    at_limit = model_with_loop(fit_mode_id, threshold, natural.iterations).fit(request)
    assert (at_limit.status, at_limit.iterations) == ("converged", natural.iterations)
    assert at_limit.parameters == natural.parameters
    below = natural.iterations - 1
    under_limit = model_with_loop(fit_mode_id, threshold, below).fit(request)
    assert (under_limit.status, under_limit.iterations) == ("iteration_limit", below)


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("fit_mode_id", "scattering"), ITERATIVE_CASES)
@pytest.mark.parametrize("end_at", [1, 2, 3])
def test_every_update_is_what_the_fit_returns_if_it_ends_there(
    monkeypatch: pytest.MonkeyPatch, fit_mode_id: str, scattering: str, end_at: int
) -> None:
    updates: list[IterationUpdate] = []
    monkeypatch.setattr(
        fit_module.PB_fit,
        "is_accuracy_reached",
        lambda self, threshold, *errors: len(updates) == end_at,
    )
    model = model_with_loop(fit_mode_id, 0.1, 5)
    result = model.fit(iterative_request(fit_mode_id, scattering, degeneracy=2.0), updates.append)
    assert (result.status, result.iterations) == ("converged", end_at)
    assert len(updates) == end_at
    for name, value in updates[-1].parameters.items():
        if name != "m1":
            assert value == result.parameters[name], name


@pytest.mark.filterwarnings("ignore")
def test_updates_of_a_hall_fit_keep_the_start_value_of_m1() -> None:
    model = registry.get("dpb")
    request = iterative_request("dpb_s_rho_rh", "acPh")
    start = dict(request.start) | {"m1": 2.0}
    updates: list[IterationUpdate] = []
    model.fit(dataclasses.replace(request, start=start), updates.append)
    assert updates
    assert all(update.parameters["m1"] == 2.0 for update in updates)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (ValueError("Initial guess is outside of provided bounds 123.456"), "fit the bounds"),
        (ValueError("Inconsistent shapes between bounds and `x0` 123.456"), "fit the bounds"),
        (ValueError("Residuals are not finite in the initial point 123.456"), "not finite"),
        (RuntimeError("Optimal parameters not found: 123.456"), "limit of function evaluations"),
        (TypeError("can't multiply 123.456"), "internal error"),
        (IndexError("index 123.456 is out of bounds"), "internal error"),
        (RecursionError("too deep 123.456"), "internal error"),
    ],
)
@pytest.mark.parametrize(("model_id", "fit_mode_id"), [("dpb", "dpb_s"), ("dpb", "dpb_s_rho")])
def test_a_failed_fit_has_a_status_and_a_safe_message(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    model_id: str,
    fit_mode_id: str,
    error: Exception,
    message: str,
) -> None:
    class Failing:
        def __getattr__(self, name: str) -> Any:
            def fail(*args: Any, **kwargs: Any) -> Any:
                raise error

            return fail

    monkeypatch.setattr(band_models, "_CORE", Failing())
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    start = default_start(fit_mode)
    result = model.fit(
        FitRequest(
            fit_mode_id,
            recorded_measurements(fit_mode),
            start,
            scattering=fit_mode.default_scattering,
        )
    )
    assert result.status == "failed"
    assert result.parameters == start
    assert result.message is not None
    assert message in result.message
    assert "123.456" not in result.message
    assert type(error).__name__ in caplog.text
    assert "123.456" not in caplog.text


@pytest.mark.filterwarnings("ignore")
def test_an_error_in_the_callback_reaches_the_caller_with_its_cause() -> None:
    class CallbackBroke(Exception):
        pass

    def broken(update: IterationUpdate) -> None:
        raise CallbackBroke from KeyError("cause")

    with pytest.raises(CallbackBroke) as caught:
        registry.get("dpb").fit(iterative_request("dpb_s_rho", "acPh"), broken)
    assert isinstance(caught.value.__cause__, KeyError)


@pytest.mark.parametrize("fit_mode_id", ["dpb_s", "dpb_s_rho"])
@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit, MemoryError])
def test_interruptions_are_not_failed_fits(
    monkeypatch: pytest.MonkeyPatch, fit_mode_id: str, error: type[BaseException]
) -> None:
    class Interrupted:
        def __getattr__(self, name: str) -> Any:
            def interrupt(*args: Any, **kwargs: Any) -> Any:
                raise error

            return interrupt

    monkeypatch.setattr(band_models, "_CORE", Interrupted())
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode(fit_mode_id)
    with pytest.raises(error):
        model.fit(
            FitRequest(
                fit_mode_id,
                recorded_measurements(fit_mode),
                default_start(fit_mode),
                scattering=fit_mode.default_scattering,
            )
        )


def test_a_failure_in_a_later_iteration_returns_the_start_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailsAfterTwoIterations:
        def __getattr__(self, name: str) -> Any:
            def fail(*args: Any, progress: fit_module.FitProgress, **kwargs: Any) -> Any:
                progress.iterations = 2
                raise ValueError("Residuals are not finite")

            return fail

    monkeypatch.setattr(band_models, "_CORE", FailsAfterTwoIterations())
    request = iterative_request("dpb_s_rho", "acPh")
    result = registry.get("dpb").fit(request)
    assert (result.status, result.iterations) == ("failed", 2)
    assert result.parameters == request.start


def real_measurement() -> Measurement:
    return Measurement(np.array([100.0, 200.0]), np.array([1e-6, 2e-6]))


@pytest.mark.parametrize(
    ("measurement", "message"),
    [
        (Measurement(np.array([]), np.array([])), "non-empty"),
        (Measurement(np.ones((2, 2)), np.ones((2, 2))), "one-dimensional"),
        (Measurement([1.0, 2.0], [1.0, 2.0]), "non-empty"),  # type: ignore[arg-type]
        (Measurement(np.array([1.0, np.nan]), np.ones(2)), "finite"),
        (Measurement(np.ones(2), np.array([1.0, np.inf])), "finite"),
        (Measurement(np.array(["a", "b"]), np.ones(2)), "finite"),
        (Measurement(np.ones(2), np.ones(3)), "different lengths"),
        (Measurement(np.array([0.0, 1.0]), np.ones(2)), "above 0 K"),
    ],
)
def test_bad_measurements_are_invalid_requests(measurement: Measurement, message: str) -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    with pytest.raises(ValueError, match=message):
        model.fit(FitRequest("dpb_s", {"seebeck": measurement}, default_start(fit_mode)))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "abc", None])
def test_start_values_must_be_finite_numbers(value: Any) -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    start = default_start(fit_mode) | {"m_eff": value}
    with pytest.raises(ValueError, match="must be a finite number"):
        model.fit(FitRequest("dpb_s", {"seebeck": real_measurement()}, start))


@pytest.mark.parametrize("bounds", [Bounds(10, 5), Bounds(5, 5), Bounds(float("nan"), 5)], ids=str)
def test_inverted_bounds_are_invalid_requests(bounds: Bounds) -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    with pytest.raises(ValueError, match="below its upper bound"):
        model.fit(
            FitRequest(
                "dpb_s",
                {"seebeck": real_measurement()},
                default_start(fit_mode),
                {"m_eff": bounds},
            )
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_degeneracy_must_be_a_finite_positive_number(value: float) -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    with pytest.raises(ValueError, match="must be positive"):
        model.fit(
            FitRequest(
                "dpb_s",
                {"seebeck": real_measurement()},
                default_start(fit_mode),
                band_2_degeneracy=value,
            )
        )


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(
    ("model_id", "fit_mode_id", "scattering"),
    [("spb", "spb_s", None), ("spb", "spb_s_rho", "acPh"), ("dpb", "dpb_s", None)],
)
def test_single_pass_fits_have_no_iterations(
    model_id: str, fit_mode_id: str, scattering: str | None
) -> None:
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    assert not fit_mode.iterative
    updates: list[IterationUpdate] = []
    result = model.fit(
        FitRequest(
            fit_mode_id,
            recorded_measurements(fit_mode),
            default_start(fit_mode),
            scattering=scattering,
        ),
        updates.append,
    )
    assert result.status == "converged"
    assert result.iterations is None
    assert updates == []


# Fits that hold chosen parameters at their start values (D30).


def fitted_names(model_id: str, fit_mode_id: str, scattering: str | None) -> list[str]:
    fit_mode = registry.get(model_id).describe().fit_mode(fit_mode_id)
    return [spec.name for spec in fit_mode.parameters_for(scattering) if spec.role == "fitted"]


def one_held_cases() -> list[tuple[str, str, str | None, str]]:
    """Each fitted parameter held alone, in modes that fit another, as holding all is an error."""
    cases = []
    for model_id, fit_mode_id, scattering in WORKING_FITS:
        names = fitted_names(model_id, fit_mode_id, scattering)
        if len(names) > 1:
            cases += [(model_id, fit_mode_id, scattering, name) for name in names]
    return cases


def fit(
    model_id: str, fit_mode_id: str, scattering: str | None, held: set[str], **extra: Any
) -> tuple[dict[str, float], Any]:
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(fit_mode_id)
    start = default_start(fit_mode)
    request = FitRequest(
        fit_mode_id,
        recorded_measurements(fit_mode),
        start,
        scattering=scattering,
        held=frozenset(held),
        **extra,
    )
    return start, model.fit(request)


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("model_id", "fit_mode_id", "scattering", "name"), one_held_cases())
def test_a_held_parameter_keeps_its_start_through_every_stage(
    model_id: str, fit_mode_id: str, scattering: str | None, name: str
) -> None:
    start, result = fit(model_id, fit_mode_id, scattering, {name})

    assert result.status in ("converged", "iteration_limit"), result.message
    assert result.parameters[name] == start[name]
    assert result.held == (name,)
    assert name not in result.parameter_errors
    assert name not in result.at_bounds
    others = set(fitted_names(model_id, fit_mode_id, scattering)) - {name}
    # The others are still fitted: at least one moves from its start.
    assert any(result.parameters[other] != start[other] for other in others)


@pytest.mark.filterwarnings("ignore")
def test_with_only_the_fermi_energy_free_nothing_else_changes() -> None:
    names = fitted_names("dpb", "dpb_s_rho", "acPh")
    held = set(names) - {"fermi_energy"}

    start, result = fit("dpb", "dpb_s_rho", "acPh", held)

    assert result.status in ("converged", "iteration_limit"), result.message
    for name in held:
        assert result.parameters[name] == start[name]
    assert result.parameters["fermi_energy"] != start["fermi_energy"]
    assert set(result.parameter_errors) <= {"fermi_energy"}


@pytest.mark.filterwarnings("ignore")
def test_a_held_parameter_fits_as_a_fit_with_it_fixed_by_hand() -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    data = recorded_measurements(fit_mode)["seebeck"]
    start, result = fit("dpb", "dpb_s", None, {"band_gap"})
    gap = start["band_gap"]
    bounds = {spec.name: spec.fit_bounds for spec in fit_mode.parameters}
    mass_bounds, fermi_bounds = bounds["m_eff"], bounds["fermi_energy"]
    assert mass_bounds is not None
    assert fermi_bounds is not None

    by_hand, _ = opt.curve_fit(
        lambda T, meff, fermi_energy: te.dpb_see_vs_temp(
            data.temperature_k, meff, gap, fermi_energy, 1.0, scal_fac=1e6
        ),
        data.temperature_k,
        data.values * 1e6,
        p0=[start["m_eff"], start["fermi_energy"]],
        bounds=(
            [mass_bounds.lower, fermi_bounds.lower],
            [mass_bounds.upper, fermi_bounds.upper],
        ),
        maxfev=1000,
    )

    assert result.parameters["m_eff"] == by_hand[0]
    assert result.parameters["fermi_energy"] == by_hand[1]


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("scattering", ["acPh", "dis", "acPhDis"])
def test_a_held_m_eff_in_a_loop_with_n2_over_n1_not_1_comes_back_as_sent(
    scattering: str,
) -> None:
    # The loop fits m_eff / N and reports it times N (D12), so a held m_eff goes in divided.
    start, result = fit(
        "dpb", "dpb_s_rho", scattering, {"m_eff"}, band_1_degeneracy=1.0, band_2_degeneracy=2.0
    )

    assert result.status in ("converged", "iteration_limit"), result.message
    assert result.parameters["m_eff"] == start["m_eff"]


@pytest.mark.filterwarnings("ignore")
def test_holding_m1_skips_the_hall_stage() -> None:
    start, result = fit("dpb", "dpb_s_rho_rh", "acPh", {"m1"})

    assert result.parameters["m1"] == start["m1"]
    assert "m1" not in result.parameter_errors


def test_a_stage_with_every_value_held_returns_its_start_unfitted() -> None:
    progress = fit_module.FitProgress(held={"see": frozenset({0, 1})})

    values, covariance = fit_module._curve_fit(
        progress,
        "see",
        lambda x, a, b: a * x + b,
        np.array([1.0, 2.0, 3.0]),
        np.array([2.0, 4.0, 6.0]),
        p0=[5.0, 7.0],
        bounds=([0.0, 0.0], [10.0, 10.0]),
    )

    assert values.tolist() == [5.0, 7.0]
    assert np.isnan(covariance).all()
    assert progress.stage_fits["see"][0].tolist() == [5.0, 7.0]


def test_a_held_value_has_no_covariance_and_the_others_are_fitted() -> None:
    x = np.linspace(0.0, 1.0, 20)
    progress = fit_module.FitProgress(held={"res": frozenset({1})})

    values, covariance = fit_module._curve_fit(
        progress,
        "res",
        lambda x, a, b, c: a * x**2 + b * x + c,
        x,
        3.0 * x**2 + 2.0 * x + 1.0,
        p0=[1.0, 2.0, 0.0],
        bounds=([-10.0, -10.0, -10.0], [10.0, 10.0, 10.0]),
    )

    assert values[1] == 2.0
    assert values[0] == pytest.approx(3.0)
    assert values[2] == pytest.approx(1.0)
    assert np.isnan(covariance[1]).all()
    assert np.isnan(covariance[:, 1]).all()
    assert math.isfinite(covariance[0, 0])


@pytest.mark.parametrize(
    ("fit_mode_id", "scattering", "held", "message"),
    [
        # A mass the SPB S fit does not find.
        ("spb_s", None, {"band_mass"}, "does not fit parameters"),
        # F belongs to dis, not acPh.
        ("dpb_s_rho", "acPh", {"F"}, "does not fit parameters"),
        ("dpb_s_rho", "acPh", {"nothing"}, "has no parameters|does not fit parameters"),
        ("spb_s", None, {"fermi_energy"}, "at least one parameter that is not held"),
    ],
)
def test_holding_what_the_fit_does_not_find_or_everything_is_an_error(
    fit_mode_id: str, scattering: str | None, held: set[str], message: str
) -> None:
    model_id = fit_mode_id.split("_")[0]
    with pytest.raises(ValueError, match=message):
        fit(model_id, fit_mode_id, scattering, held)
