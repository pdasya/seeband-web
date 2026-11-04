import hashlib
import importlib.util
import json
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
PACKAGE = Path(__file__).parents[1]
EXAMPLES = ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]
GOLDEN = {
    name: json.loads((FIXTURES / "golden" / f"{name}.json").read_text(encoding="utf-8"))
    for name in EXAMPLES
}
NETS = json.loads((FIXTURES / "neural_net_references.json").read_text(encoding="utf-8"))
TABLE = json.loads(
    (resources.files("seeband_core") / "data" / "desktop_modes.json").read_text(encoding="utf-8")
)
MODES = {mode["id"]: mode for mode in TABLE["modes"]}
RUNS = [(name, run) for name, document in GOLDEN.items() for run in document["runs"]]
OK_RUNS = [(name, run) for name, run in RUNS if run["status"] == "ok"]
RUN_IDS = [f"{name}-{run['mode']}-{run['scattering']}" for name, run in RUNS]
OK_IDS = [f"{name}-{run['mode']}-{run['scattering']}" for name, run in OK_RUNS]
SCATTERED = {"spb_s_rho", "spb_s_rho_rh", "dpb_s_rho", "dpb_s_rho_rh"}
# Positions of the arguments in each fit call, from the fitting threads in seeband.py.
SEE_ARGS = {
    "spb_s": (3, 4),
    "spb_s_rho": (5, 6),
    "dpb_s": (2, 3),
    "dpb_s_rho": (4, 5),
    "dpb_s_rho_rh": (6, 7),
}
RES_ARGS = {"spb_s_rho": (7, 8), "dpb_s_rho": (6, 7), "dpb_s_rho_rh": (8, 9)}
RES_ORDER = {
    "spb_s_rho": ["A", "C", "F"],
    "dpb_s_rho": ["A", "B", "C", "D", "F", "G"],
    "dpb_s_rho_rh": ["A", "B", "C", "D", "F", "G"],
}
SEE_ORDER = {"spb": ["fermi_energy"], "dpb": ["m_eff", "band_gap", "fermi_energy"]}
WINDOW = {"dpb_s": "dpb_see", "dpb_s_rho": "dpb_res", "dpb_s_rho_rh": "dpb_hall"}

# PINNED-START
# Copied from the capture to detect accidental changes. These are not an independent reference.
FILE_SHA256: dict[str, str] = {
    "01_Fe2VAl09Si01": "0e18fbf0af37f5ceb4a4a7b6e3e6aff188cce017ec70986a55001204e4954cff",
    "02_SiP": "479fe4890928ac8a3695a5f469ec39848af40a27dfda9c27abc8474a6d6ef1c4",
    "03_AWI32_SI": "98ba3f82d5c4b2356853a329e1a87302258c786449bed898182be510f3549a89",
}
PINNED: dict[str, dict[tuple[str, str | None], list[float]]] = {
    "01_Fe2VAl09Si01": {
        ("spb_s", None): [1677.4],
        ("spb_s_rho", "acPh"): [-3000.0, 56412.0, 100.0, 4000.0],
        ("spb_s_rho", "dis"): [-3000.0, 40000.0, 100.0, 131.92],
        ("spb_s_rho", "acPhDis"): [-3000.0, 69929.0, 0.41127, 4000.0],
        ("dpb_s", None): [1.2408, 655.34, 1296.3],
        ("dpb_s_rho", "acPh"): [1.2565, 651.55, 1292.3, 292300.0, 1.0355, 1.0, 1.0, 1000.0, 1.0],
        ("dpb_s_rho", "dis"): [1.9686, 528.91, 1162.6, 40000.0, 1.0, 1.0, 1.0, 643.81, 2.0],
        ("dpb_s_rho", "acPhDis"): [1.7257, 562.26, 1197.9, 519730.0, 1.1, 2.0, 0.5, 1000.0, 1.0],
        ("dpb_s_rho_rh", "acPh"): [
            1.2565,
            651.55,
            1292.3,
            292300.0,
            1.0355,
            1.0,
            1.0,
            1000.0,
            1.0,
            5.9969,
        ],
        ("dpb_s_rho_rh", "acPhDis"): [
            1.7257,
            562.26,
            1197.9,
            519730.0,
            1.1,
            2.0,
            0.5,
            1000.0,
            1.0,
            4.4006,
        ],
    },
    "02_SiP": {
        ("spb_s", None): [3.7587],
        ("spb_s_rho", "acPh"): [-3000.0, 2.1741, 100.0, 4000.0],
        ("spb_s_rho", "dis"): [-3000.0, 40000.0, 100.0, 1.0],
        ("spb_s_rho", "acPhDis"): [-3000.0, 1160.5, 1000.0, 4000.0],
        ("dpb_s", None): [4.1897e-07, 1002.2, -113.93],
        ("dpb_s_rho", "acPh"): [4.1897e-07, 1002.2, -113.93, 40000.0, 1.0, 1.0, 1.0, 1000.0, 1.0],
        ("dpb_s_rho", "dis"): [4.1897e-07, 1002.2, -113.93, 40000.0, 1.0, 1.0, 1.0, 1000.0, 1.0],
        ("dpb_s_rho", "acPhDis"): [
            4.1897e-07,
            1002.2,
            -113.93,
            40000.0,
            1.0,
            1.0,
            1.0,
            1000.0,
            1.0,
        ],
        ("dpb_s_rho_rh", "acPh"): [
            4.1897e-07,
            1002.2,
            -113.93,
            40000.0,
            1.0,
            1.0,
            1.0,
            1000.0,
            1.0,
            10.0,
        ],
        ("dpb_s_rho_rh", "acPhDis"): [
            4.1897e-07,
            1002.2,
            -113.93,
            40000.0,
            1.0,
            1.0,
            1.0,
            1000.0,
            1.0,
            10.0,
        ],
    },
    "03_AWI32_SI": {
        ("spb_s", None): [3000.0],
        ("spb_s_rho", "acPh"): [-351.49, 100070.0, 100.0, 4000.0],
        ("spb_s_rho", "dis"): [-351.49, 40000.0, 100.0, 237.37],
        ("spb_s_rho", "acPhDis"): [-351.49, 10000000.0, 139.24, 4000.0],
        ("dpb_s", None): [1.3187, 1878.2, -258.95],
        ("dpb_s_rho", "acPh"): [1.3923, 1898.5, -259.01, 111920.0, 1.1, 1.0, 1.0, 1000.0, 1.0],
        ("dpb_s_rho", "dis"): [1.4206, 1906.1, -259.03, 40000.0, 1.0, 1.0, 1.0, 307.35, 1.2233],
        ("dpb_s_rho", "acPhDis"): [1.8352, 2004.6, -259.31, 281940.0, 1.1, 2.0, 0.5, 1000.0, 1.0],
        ("dpb_s_rho_rh", "acPh"): [
            1.3923,
            1898.5,
            -259.01,
            111920.0,
            1.1,
            1.0,
            1.0,
            1000.0,
            1.0,
            1.2368,
        ],
        ("dpb_s_rho_rh", "acPhDis"): [
            1.8352,
            2004.6,
            -259.31,
            281940.0,
            1.1,
            2.0,
            0.5,
            1000.0,
            1.0,
            1.2266,
        ],
    },
}
D1_PINNED: dict[str, list[float]] = {
    "01_Fe2VAl09Si01": [0.0025409, 2377.3, 3000.0, 40000.0, 1.0, 1.0, 1.0, 0.024658, 69.144, 10.0],
    "02_SiP": [4.1897e-07, 1002.2, -113.93, 40000.0, 1.0, 1.0, 1.0, 1000.0, 1.0, 10.0],
    "03_AWI32_SI": [1.4206, 1906.1, -259.03, 40000.0, 1.0, 1.0, 1.0, 307.35, 1.2232, 1.2287],
}
# PINNED-END


def parameters(mode_id: str) -> dict[str, dict[str, Any]]:
    return {p["name"]: p for p in MODES[mode_id]["parameters"]}


def bounds_of(mode_id: str, names: list[str]) -> tuple[list[float], list[float]]:
    table = parameters(mode_id)
    return (
        [table[name]["default_fit_bounds"]["lower"] for name in names],
        [table[name]["default_fit_bounds"]["upper"] for name in names],
    )


def assert_bounds(actual: list[list[float]], expected: tuple[list[float], list[float]]) -> None:
    assert actual[0] == pytest.approx(expected[0])
    assert actual[1] == pytest.approx(expected[1])


def run_of(name: str, mode: str, scattering: str | None) -> dict[str, Any]:
    return next(
        run
        for run in GOLDEN[name]["runs"]
        if run["mode"] == mode and run["scattering"] == scattering
    )


CALLED = [(name, run) for name, run in RUNS if run["calls"]]
CALLED_IDS = [f"{name}-{run['mode']}-{run['scattering']}" for name, run in CALLED]


@pytest.mark.parametrize("name", EXAMPLES)
def test_files_are_unchanged(name: str) -> None:
    content = (FIXTURES / "golden" / f"{name}.json").read_bytes()
    assert hashlib.sha256(content).hexdigest() == FILE_SHA256[name]


@pytest.mark.parametrize("name", EXAMPLES)
def test_environment_and_inputs_are_recorded(name: str) -> None:
    document = GOLDEN[name]
    for key in ("python", "numpy", "scipy", "mpmath", "tensorflow", "qt", "pyqt", "pyqtgraph"):
        assert document["environment"][key]
    assert document["source"]["commit"] == TABLE["source"]["commit"]
    assert set(document["input_files_sha256"]) == {"see", "rho", "hall"}


@pytest.mark.parametrize("name", EXAMPLES)
def test_every_mode_and_scattering_was_run(name: str) -> None:
    found = {(run["mode"], run["scattering"]) for run in GOLDEN[name]["runs"]}
    expected = {("spb_s", None), ("dpb_s", None)}
    expected |= {(mode, s) for mode in SCATTERED for s in ("acPh", "dis", "acPhDis")}
    assert found == expected


@pytest.mark.parametrize(("name", "run"), RUNS, ids=RUN_IDS)
def test_status_matches_known_failures(name: str, run: dict[str, Any]) -> None:
    if run["mode"] == "spb_s_rho_rh":
        assert run["status"] == "fails_before_calculation"
        assert "fermi_slider_spb" in run["printed_error"]
        assert run["calls"] == []
    elif run["mode"] == "dpb_s_rho_rh" and run["scattering"] == "dis":
        assert run["status"] == "fails_in_dpb_see_res_hall_fit"
        assert run["printed_error"] == "Initial guess is outside of provided bounds"
    else:
        assert run["status"] == "ok"
        assert run["printed_error"] is None


@pytest.mark.parametrize(("name", "run"), OK_RUNS, ids=OK_IDS)
def test_successful_runs_record_fit_and_curve(name: str, run: dict[str, Any]) -> None:
    fit, calc = run["calls"]
    assert fit["function"] == MODES[run["mode"]]["fit_function"]
    assert calc["function"] == MODES[run["mode"]]["calc_function"]
    assert run["emitted"][-1] == fit["result"]
    assert run["emitted"][:-1] == calc["result"]
    assert len(run["emitted"][0]) == TABLE["curve_points"]["count"]
    assert run["manual_curve_calls"][0]["function"] == MODES[run["mode"]]["calc_function"]


@pytest.mark.parametrize(("name", "run"), OK_RUNS, ids=OK_IDS)
def test_iterative_runs_record_how_they_stopped(name: str, run: dict[str, Any]) -> None:
    iteration = MODES[run["mode"]]["iteration"]
    if iteration["kind"] == "iterative":
        assert run["stopped_by"] == "accuracy"
        assert 1 <= run["iterations"] <= iteration["max_iterations"]
        partial = run["scattering"] == "acPhDis"
        assert run["stop_path"] == ("c_and_d_only" if partial else "all_band_and_first_scattering")
    else:
        assert run["stopped_by"] is None
        assert run["iterations"] is None
        assert run["stop_path"] is None


@pytest.mark.parametrize(("name", "run"), CALLED, ids=CALLED_IDS)
def test_table_matches_what_the_window_passed(name: str, run: dict[str, Any]) -> None:
    mode_id = run["mode"]
    args = run["calls"][0]["args"]
    model = MODES[mode_id]["model"].lower()
    table = parameters(mode_id)
    see_start, see_limits = SEE_ARGS[mode_id]
    names = SEE_ORDER[model]
    assert_bounds(args[see_limits], bounds_of(mode_id, names))
    if model == "spb":
        # SPB start values come from the slider defaults, with the mass just before them.
        fermi = table["fermi_energy"]
        assert args[see_start] == [fermi["slider"]["default"] * fermi["fit_scale"]]
        mass = table["band_mass"]
        assert args[see_start - 1] == pytest.approx(mass["slider"]["default"] * mass["fit_scale"])
    else:
        # DPB start values come from the sliders after the neural net ran.
        start = GOLDEN[name]["start_values"][WINDOW[mode_id]]
        assert args[see_start] == pytest.approx(
            [start["m_eff"], start["band_gap_k"], start["fermi_energy_k"]]
        )
        # Sliders hold integers, so a value divided by its scale must be one in the slider range.
        for parameter_name, value in zip(names, args[see_start], strict=True):
            slider = table[parameter_name]["slider"]
            position = value / table[parameter_name]["fit_scale"]
            assert position == pytest.approx(round(position))
            assert slider["min"] <= round(position) <= slider["max"]
    if mode_id in RES_ARGS:
        start_index, limits = RES_ARGS[mode_id]
        names = RES_ORDER[mode_id]
        assert_bounds(args[limits], bounds_of(mode_id, names))
        expected = [table[n]["slider"]["default"] * table[n]["fit_scale"] for n in names]
        assert args[start_index] == pytest.approx(expected)
    if mode_id == "dpb_s_rho_rh":
        m1 = table["m1"]
        assert args[10] == pytest.approx(m1["slider"]["default"] * m1["fit_scale"])
        bounds = m1["default_fit_bounds"]
        assert args[11] == [[bounds["lower"]], [bounds["upper"]]]


@pytest.mark.parametrize("name", EXAMPLES)
def test_failing_hall_run_has_g_start_outside_its_bounds(name: str) -> None:
    args = run_of(name, "dpb_s_rho_rh", "dis")["calls"][0]["args"]
    assert args[8][-1] == 1.0
    assert (args[9][0][-1], args[9][1][-1]) == (50, 200)


@pytest.mark.parametrize(("name", "run"), CALLED, ids=CALLED_IDS)
def test_table_matches_iteration_settings_the_window_passed(name: str, run: dict[str, Any]) -> None:
    iteration = MODES[run["mode"]]["iteration"]
    if iteration["kind"] == "iterative":
        threshold, limit = run["calls"][0]["args"][-3:-1]
        assert threshold == iteration["threshold"]
        assert limit == iteration["max_iterations"]


@pytest.mark.parametrize("name", EXAMPLES)
def test_real_window_matches_neural_net_references(name: str) -> None:
    case = next(case for case in NETS["cases"] if case["name"] == name)
    for window in ("dpb_see", "dpb_res", "dpb_hall"):
        assert GOLDEN[name]["start_values"][window] == case["desktop_start_values"]


@pytest.mark.parametrize("name", EXAMPLES)
def test_double_factor_of_d5_is_recorded(name: str) -> None:
    call = run_of(name, "spb_s_rho_rh", "acPhDis")["manual_curve_calls"][0]
    assert call["args"][5] == [40000, 30000, 4000]
    other = run_of("01_Fe2VAl09Si01", "spb_s_rho", "acPhDis")["manual_curve_calls"][0]
    assert other["args"][5] == [40000, 100, 4000]
    assert min(call["result"][2]) > 10 * max(other["result"][2])


@pytest.mark.parametrize("name", EXAMPLES)
def test_results_match_recorded_values(name: str) -> None:
    for (mode, scattering), expected in PINNED[name].items():
        result = run_of(name, mode, scattering)["calls"][0]["result"]
        assert result == pytest.approx(expected, rel=1e-3, abs=1e-6)


@pytest.mark.parametrize("name", EXAMPLES)
def test_g_minimum_case_matches_recorded_values(name: str) -> None:
    block = GOLDEN[name]["d1_with_g_minimum_1"]
    assert block["status"] == "ok"
    args = block["calls"][0]["args"]
    assert (args[9][0][-1], args[9][1][-1]) == (1, 200)
    assert block["calls"][0]["result"] == pytest.approx(D1_PINNED[name], rel=1e-3, abs=1e-6)


def test_summary_page_matches_the_results() -> None:
    path = PACKAGE / "scripts" / "summarize_golden_results.py"
    spec = importlib.util.spec_from_file_location("summarize_golden_results", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    page = (PACKAGE / "docs" / "golden-results-summary.md").read_text(encoding="utf-8")
    assert page == module.render(GOLDEN, TABLE)
