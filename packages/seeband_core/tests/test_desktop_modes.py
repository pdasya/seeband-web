import json
import re
from importlib import resources
from typing import Any

import pytest

SOURCE = re.compile(r"^(seeband\.py|modules/fit_module\.py):\d+$")
MODE_IDS = {"spb_s", "spb_s_rho", "spb_s_rho_rh", "dpb_s", "dpb_s_rho", "dpb_s_rho_rh"}


@pytest.fixture(scope="module")
def table() -> dict[str, Any]:
    path = resources.files("seeband_core") / "data" / "desktop_modes.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def modes(table: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {mode["id"]: mode for mode in table["modes"]}


def test_all_modes_are_present(table: dict[str, Any]) -> None:
    assert set(modes(table)) == MODE_IDS


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


@pytest.mark.parametrize("mode_id", ["spb_s", "spb_s_rho", "spb_s_rho_rh", "dpb_s"])
def test_single_pass_modes_are_marked(table: dict[str, Any], mode_id: str) -> None:
    assert modes(table)[mode_id]["iteration"]["kind"] == "single_pass"


def test_every_value_cites_a_source(table: dict[str, Any]) -> None:
    def assert_sources(refs: list[str]) -> None:
        assert refs
        assert all(SOURCE.match(ref) for ref in refs)

    for mode in table["modes"]:
        assert_sources(mode["fit_call"])
        assert_sources(mode["iteration"]["source"])
        assert_sources(mode["maxfev"]["source"])
        for parameter in mode["parameters"]:
            assert_sources([parameter["slider"]["source"]])
            assert_sources([parameter["line_edit"]["source"]])
            assert_sources(parameter["fit_start_source"])
            assert_sources(parameter["calc_source"])
            if parameter["role"] == "fitted":
                assert_sources(parameter["fit_bounds"]["source"])
    for deviation in table["deviations"]:
        assert_sources(deviation["source"])


def test_slider_defaults_are_inside_their_ranges(table: dict[str, Any]) -> None:
    for mode in table["modes"]:
        for parameter in mode["parameters"]:
            slider = parameter["slider"]
            assert slider["min"] <= slider["default"] <= slider["max"], slider["widget"]


def test_deviation_references_exist(table: dict[str, Any]) -> None:
    ids = {deviation["id"] for deviation in table["deviations"]}
    for mode in table["modes"]:
        if "status_reason" in mode:
            assert mode["status_reason"] in ids
        for parameter in mode["parameters"]:
            if "web_fit_bounds" in parameter:
                assert parameter["web_fit_bounds"]["reason"] in ids


def test_dpb_hall_g_records_the_deviation(table: dict[str, Any]) -> None:
    parameters = {p["name"]: p for p in modes(table)["dpb_s_rho_rh"]["parameters"]}
    g = parameters["G"]
    assert (g["fit_bounds"]["lower"], g["fit_bounds"]["upper"]) == (50, 200)
    assert (g["web_fit_bounds"]["lower"], g["web_fit_bounds"]["upper"]) == (0.5, 2)
