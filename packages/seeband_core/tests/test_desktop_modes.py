import json
import re
from collections.abc import Iterator
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

SOURCE = re.compile(r"^(seeband\.py|modules/(fit_module|neural_nets|data_processing)\.py):\d+$")
DOC = Path(__file__).parents[1] / "docs" / "desktop-modes.md"
SCATTERING = {"acPh", "dis", "acPhDis"}

# Expected values, written separately from the table so that an accidental edit fails.
# name: (display_scale, fit_scale, calc_scale, lower bound, upper bound, scattering)
ALL = SCATTERING
AC = {"acPh", "acPhDis"}
BOTH = {"acPhDis"}
DIS = {"dis"}
DPB_BAND = {
    "m_eff": (0.01, 0.01, 0.01, -3, 3, ALL),
    "band_gap": (1, 1, 1, -3000, 3000, ALL),
    "fermi_energy": (1, 1, 1, -3000, 3000, ALL),
}
DPB_RES = {
    "A": (1, 1, 1, 0, 1000000, AC),
    "B": (0.01, 0.01, 0.01, 0.9, 1.1, AC),
    "C": (0.01, 0.01, 0.01, 0.5, 2, BOTH),
    "D": (0.01, 0.01, 0.01, 0.5, 2, BOTH),
    "F": (1, 1, 1, 0, 100000, DIS),
}
SPB_FERMI = {"fermi_energy": (1, 1, 1, -3000, 3000, ALL)}
EXPECTED: dict[str, dict[str, tuple[Any, ...]]] = {
    "spb_s": {"band_mass": (0.01, 0.01, 0.01, None, None, ALL), **SPB_FERMI},
    "spb_s_rho": {
        "band_mass": (0.01, 0.01, 0.01, None, None, ALL),
        **SPB_FERMI,
        "A": (1, 1, 1, 1, 10000000, AC),
        "C": (0.01, 1, 1, 0.001, 1000, BOTH),
        "F": (1, 1, 1, 1, 10000000, DIS),
    },
    "spb_s_rho_rh": {
        "band_mass": (0.01, 1, 0.01, -300, 300, ALL),
        **SPB_FERMI,
        "A": (1, 1, 1, 1, 10000000, AC),
        "C": (0.01, 1, 300, 0.001, 1000, BOTH),
        "F": (1, 1, 1, 1, 10000000, DIS),
    },
    "dpb_s": DPB_BAND,
    "dpb_s_rho": {**DPB_BAND, **DPB_RES, "G": (0.01, 0.01, 0.01, 0.5, 2, DIS)},
    "dpb_s_rho_rh": {
        **DPB_BAND,
        **DPB_RES,
        "G": (0.01, 0.01, 0.01, 50, 200, DIS),
        "m1": (0.01, 0.01, 0.01, 0.1, 10, ALL),
    },
}
EXPECTED_MAXFEV = {
    "spb_s": {"see": 1000},
    "spb_s_rho": {"see": 1000, "rho": 50000},
    "spb_s_rho_rh": {"see": 1000, "rho": 50000, "hall": 5000},
    "dpb_s": {"see": 1000},
    "dpb_s_rho": {"see": 1000, "rho": 50000},
    "dpb_s_rho_rh": {"see": 1000, "rho": 50000, "hall": 5000},
}
EXPECTED_CALC_PATHS = {
    "spb_s_rho": (1, 1, 0.01, 0.01),
    "spb_s_rho_rh": (300, 1, 0.01, 0.01),
    "dpb_s_rho": (0.01, 0.01, 1, 1),
    "dpb_s_rho_rh": (0.01, 0.01, 1, 1),
}
EXPECTED_MASKS = {
    "spb_s": ["x_mask"],
    "spb_s_rho": ["x_mask"],
    "spb_s_rho_rh": ["x_mask"],
    "dpb_s": ["x_mask"],
    "dpb_s_rho": ["x_mask", "x_mask_res"],
    "dpb_s_rho_rh": ["x_mask", "x_mask_res", "x_mask_hall"],
}


@pytest.fixture(scope="module")
def table() -> dict[str, Any]:
    path = resources.files("seeband_core") / "data" / "desktop_modes.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def modes(table: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {mode["id"]: mode for mode in table["modes"]}


def parameters(mode: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {parameter["name"]: parameter for parameter in mode["parameters"]}


def citations(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key != "source" or not isinstance(value, dict):
                if key.endswith("source") and value is not None:
                    yield from [value] if isinstance(value, str) else value
                    continue
            yield from citations(value)
    elif isinstance(node, list):
        for item in node:
            yield from citations(item)


def test_all_modes_are_present(table: dict[str, Any]) -> None:
    assert set(modes(table)) == set(EXPECTED)


@pytest.mark.parametrize("mode_id", EXPECTED)
def test_parameters_match_expected_values(table: dict[str, Any], mode_id: str) -> None:
    actual = {}
    for name, parameter in parameters(modes(table)[mode_id]).items():
        bounds = parameter["default_fit_bounds"]
        actual[name] = (
            parameter["display_scale"],
            parameter["fit_scale"],
            parameter["calc_scale"],
            bounds["lower"] if bounds else None,
            bounds["upper"] if bounds else None,
            set(parameter["scattering"]),
        )
    assert actual == EXPECTED[mode_id]


@pytest.mark.parametrize("mode_id", EXPECTED)
def test_maxfev_matches_expected_values(table: dict[str, Any], mode_id: str) -> None:
    maxfev = {k: v for k, v in modes(table)[mode_id]["maxfev"].items() if k != "source"}
    assert maxfev == EXPECTED_MAXFEV[mode_id]


@pytest.mark.parametrize(
    ("mode_id", "threshold", "limit"),
    [("dpb_s_rho", 0.1, 1000), ("dpb_s_rho_rh", 0.1, 20)],
)
def test_iterative_modes_keep_desktop_settings(
    table: dict[str, Any], mode_id: str, threshold: float, limit: int
) -> None:
    iteration = modes(table)[mode_id]["iteration"]
    assert iteration["kind"] == "iterative"
    assert iteration["threshold"] == threshold
    assert iteration["max_iterations"] == limit
    assert iteration["stop_rule"]
    assert iteration["on_limit"]


@pytest.mark.parametrize("mode_id", ["spb_s", "spb_s_rho", "spb_s_rho_rh", "dpb_s"])
def test_single_pass_modes_are_marked(table: dict[str, Any], mode_id: str) -> None:
    assert modes(table)[mode_id]["iteration"]["kind"] == "single_pass"


@pytest.mark.parametrize("mode_id", EXPECTED_CALC_PATHS)
def test_calc_paths_match_expected_values(table: dict[str, Any], mode_id: str) -> None:
    paths = modes(table)[mode_id]["calc_paths"]["paths"]
    order = ("slider_handler", "line_edit", "startup_curve", "data_export")
    assert tuple(paths[name]["scale"] for name in order) == EXPECTED_CALC_PATHS[mode_id]
    handler_scale = paths["slider_handler"]["scale"]
    assert parameters(modes(table)[mode_id])["C"]["calc_scale"] == handler_scale


def test_mask_updates_match_expected_values(table: dict[str, Any]) -> None:
    updates = table["fit_range"]["mask_updates"]
    assert {mode_id: update["masks"] for mode_id, update in updates.items()} == EXPECTED_MASKS


def test_every_citation_is_well_formed(table: dict[str, Any]) -> None:
    refs = list(citations(table))
    assert len(refs) > 300
    assert [ref for ref in refs if not SOURCE.match(ref)] == []


def test_fitted_parameters_have_bounds_and_origin(table: dict[str, Any]) -> None:
    for mode in table["modes"]:
        for parameter in mode["parameters"]:
            if parameter["role"] == "fitted":
                assert parameter["bounds_origin"] in {"slider_range", "constant"}
                assert parameter["default_fit_bounds"]["source"]
                assert parameter["editable"] == bool(parameter["edit_source"])
                if parameter["bounds_origin"] == "constant":
                    assert parameter["editable"] is False


def test_slider_defaults_are_inside_their_ranges(table: dict[str, Any]) -> None:
    for mode in table["modes"]:
        for parameter in mode["parameters"]:
            slider = parameter["slider"]
            assert slider["min"] <= slider["default"] <= slider["max"], slider["widget"]


def test_default_start_values_are_inside_bounds(table: dict[str, Any]) -> None:
    for mode in table["modes"]:
        for parameter in mode["parameters"]:
            bounds = parameter.get("web_fit_bounds") or parameter["default_fit_bounds"]
            if bounds:
                fit_scale = parameter.get("web_fit_scale", parameter["fit_scale"])
                start = parameter["slider"]["default"] * fit_scale
                assert bounds["lower"] <= start <= bounds["upper"], parameter["slider"]["widget"]


def test_scattering_lists_are_valid(table: dict[str, Any]) -> None:
    for mode in table["modes"]:
        for parameter in mode["parameters"]:
            assert parameter["scattering"]
            assert set(parameter["scattering"]) <= SCATTERING


def test_deviation_references_exist(table: dict[str, Any]) -> None:
    ids = {deviation["id"] for deviation in table["deviations"]}
    for mode in table["modes"]:
        if "status_reason" in mode:
            assert mode["status_reason"] in ids
        for parameter in mode["parameters"]:
            if "web_fit_bounds" in parameter:
                assert parameter["web_fit_bounds"]["reason"] in ids


def test_dpb_hall_g_records_the_deviation(table: dict[str, Any]) -> None:
    g = parameters(modes(table)["dpb_s_rho_rh"])["G"]
    assert (g["default_fit_bounds"]["lower"], g["default_fit_bounds"]["upper"]) == (50, 200)
    assert (g["web_fit_bounds"]["lower"], g["web_fit_bounds"]["upper"]) == (0.5, 2)


def test_page_matches_the_table(table: dict[str, Any]) -> None:
    page = DOC.read_text(encoding="utf-8")
    for mode in table["modes"]:
        title = mode["fit_mode"].replace("S+rho", "S + ρ").replace("+R_H", " + R_H")
        heading = f"## {mode['model']}, {title}\n"
        assert heading in page, heading
        section = page.split(heading, 1)[1].split("\n## ", 1)[0]
        for parameter in mode["parameters"]:
            assert f"`{parameter['name']}`" in section
            bounds = parameter["default_fit_bounds"]
            expected = f"{bounds['lower']} to {bounds['upper']}" if bounds else "not fitted"
            assert expected in section, parameter["name"]
    for deviation in table["deviations"]:
        assert f"| {deviation['id']} " in page
        assert deviation["title"] in page
