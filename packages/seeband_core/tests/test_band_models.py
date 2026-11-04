import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core.band_models import parabolic_band
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    Bounds,
    CurveKind,
    CurveRequest,
    FitMode,
    FitRequest,
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
def test_every_curve_runs_and_names_its_unit(
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

    assert set(result.parameters) == set(start)
    assert start == start_before
    for name, data in measurements.items():
        assert np.array_equal(data.values, values_before[name])
    for spec in fit_mode.parameters:
        if spec.role == "fixed":
            assert result.parameters[spec.name] == start[spec.name]


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
    assert 0.5 <= result.parameters["G"] <= 2
    with pytest.raises(ValueError, match="bounds"):
        model.fit(
            FitRequest(
                "dpb_s_rho_rh",
                measurements,
                start,
                bounds={"G": Bounds(50, 200)},
                scattering="dis",
            )
        )


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
    with pytest.raises(ValueError):
        model.fit(FitRequest("spb_s_rho_rh", measurements, start, scattering="acPh"))
    with pytest.raises(TypeError):
        model.fit(
            FitRequest("spb_s_rho_rh", measurements, start | {"band_mass": -1.5}, scattering="acPh")
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


def test_band_diagram_is_available_without_a_model() -> None:
    wavevector, energy = parabolic_band(-1.0, 1.0, 3, 1.0, 5.0)
    assert wavevector.tolist() == [-1.0, 0.0, 1.0]
    assert energy[1] == 5.0


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
