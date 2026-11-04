import json
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES = ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]
GOLDEN = {name: json.loads((FIXTURES / "golden" / f"{name}.json").read_text()) for name in EXAMPLES}
NETS = json.loads((FIXTURES / "neural_net_references.json").read_text())
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
RES_ARGS = {"spb_s_rho": (7, 8), "dpb_s_rho": (6, 7), "dpb_s_rho_rh": (8, 9)}
SEE_ARGS = {
    "spb_s": (3, 4),
    "spb_s_rho": (5, 6),
    "dpb_s": (2, 3),
    "dpb_s_rho": (4, 5),
    "dpb_s_rho_rh": (6, 7),
}
RES_ORDER = {
    "spb_s_rho": ["A", "C", "F"],
    "dpb_s_rho": ["A", "B", "C", "D", "F", "G"],
    "dpb_s_rho_rh": ["A", "B", "C", "D", "F", "G"],
}
SEE_ORDER = {"spb": ["fermi_energy"], "dpb": ["m_eff", "band_gap", "fermi_energy"]}
# Written separately from the fixtures, rounded to 3 significant places of interest.
EXPECTED_01 = {
    ("spb_s", None): [1677.426],
    ("spb_s_rho", "acPh"): [-3000.0, 56412.336, 100, 4000],
    ("dpb_s", None): [1.241, 655.338, 1296.289],
    ("dpb_s_rho", "acPh"): [1.256, 651.554, 1292.300, 292304.233, 1.036, 1.0, 1.0, 1000, 1.0],
    ("dpb_s_rho", "acPhDis"): [1.726, 562.256, 1197.932, 519731.243, 1.1, 2.0, 0.5, 1000, 1.0],
    ("dpb_s_rho_rh", "acPh"): [
        1.256, 651.554, 1292.300, 292304.233, 1.036, 1.0, 1.0, 1000, 1.0, 5.997,
    ],
}  # fmt: skip


def parameters(mode_id: str) -> dict[str, dict[str, Any]]:
    return {p["name"]: p for p in MODES[mode_id]["parameters"]}


def bounds_of(mode_id: str, names: list[str]) -> tuple[list[float], list[float]]:
    table = parameters(mode_id)
    return (
        [table[name]["default_fit_bounds"]["lower"] for name in names],
        [table[name]["default_fit_bounds"]["upper"] for name in names],
    )


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


@pytest.mark.parametrize("name", EXAMPLES)
def test_lowering_g_minimum_makes_dpb_hall_dis_run(name: str) -> None:
    assert GOLDEN[name]["d1_with_g_minimum_1"]["status"] == "ok"


@pytest.mark.parametrize(("name", "run"), OK_RUNS, ids=OK_IDS)
def test_successful_runs_record_fit_and_curve(name: str, run: dict[str, Any]) -> None:
    fit, calc = run["calls"]
    assert fit["function"] == MODES[run["mode"]]["fit_function"]
    assert calc["function"] == MODES[run["mode"]]["calc_function"]
    assert run["emitted"][-1] == fit["result"]
    assert len(run["emitted"][0]) == TABLE["curve_points"]["count"]
    assert run["manual_curve_calls"][0]["function"] == MODES[run["mode"]]["calc_function"]


@pytest.mark.parametrize(("name", "run"), OK_RUNS, ids=OK_IDS)
def test_iterative_runs_record_why_they_stopped(name: str, run: dict[str, Any]) -> None:
    kind = MODES[run["mode"]]["iteration"]["kind"]
    assert run["stopped_by"] == ("accuracy" if kind == "iterative" else None)


def assert_bounds(actual: list[list[float]], expected: tuple[list[float], list[float]]) -> None:
    assert actual[0] == pytest.approx(expected[0])
    assert actual[1] == pytest.approx(expected[1])


@pytest.mark.parametrize(("name", "run"), OK_RUNS, ids=OK_IDS)
def test_table_matches_bounds_the_window_passed(name: str, run: dict[str, Any]) -> None:
    mode_id = run["mode"]
    args = run["calls"][0]["args"]
    model = MODES[mode_id]["model"].lower()
    table = parameters(mode_id)
    see_start, see_limits = SEE_ARGS[mode_id]
    names = SEE_ORDER[model]
    assert_bounds(args[see_limits], bounds_of(mode_id, names))
    assert len(args[see_start]) == len(names)
    if model == "spb":
        # The band mass comes just before the Seebeck start value in SPB fits.
        mass = table["band_mass"]
        assert args[see_start - 1] == pytest.approx(mass["slider"]["default"] * mass["fit_scale"])
    if mode_id in RES_ARGS:
        start, limits = RES_ARGS[mode_id]
        names = RES_ORDER[mode_id]
        assert_bounds(args[limits], bounds_of(mode_id, names))
        expected = [table[n]["slider"]["default"] * table[n]["fit_scale"] for n in names]
        assert args[start] == pytest.approx(expected)
    if mode_id == "dpb_s_rho_rh":
        m1 = table["m1"]
        assert args[10] == pytest.approx(m1["slider"]["default"] * m1["fit_scale"])
        assert args[11] == [
            [m1["default_fit_bounds"]["lower"]],
            [m1["default_fit_bounds"]["upper"]],
        ]


@pytest.mark.parametrize("name", EXAMPLES)
def test_table_matches_g_bounds_of_the_failing_hall_run(name: str) -> None:
    run = next(
        run
        for run in GOLDEN[name]["runs"]
        if run["mode"] == "dpb_s_rho_rh" and run["scattering"] == "dis"
    )
    limits = run["calls"][0]["args"][9]
    g = parameters("dpb_s_rho_rh")["G"]["default_fit_bounds"]
    assert (limits[0][-1], limits[1][-1]) == (g["lower"], g["upper"])
    assert run["calls"][0]["args"][8][-1] == 1.0


@pytest.mark.parametrize("name", EXAMPLES)
def test_table_matches_iteration_settings_the_window_passed(name: str) -> None:
    for run in GOLDEN[name]["runs"]:
        iteration = MODES[run["mode"]]["iteration"]
        if iteration["kind"] == "iterative":
            threshold, limit = run["calls"][0]["args"][-3:-1]
            assert threshold == iteration["threshold"]
            assert limit == iteration["max_iterations"]


@pytest.mark.parametrize("name", EXAMPLES)
def test_real_window_matches_neural_net_references(name: str) -> None:
    sliders = GOLDEN[name]["start_sliders"]
    case = next(case for case in NETS["cases"] if case["name"] == name)
    start = case["desktop_start_values"]
    for window in ("dpb_see", "dpb_res", "dpb_hall"):
        assert sliders[window]["mass"] / 100 == start["m_eff"]
        assert sliders[window]["band_gap"] == start["band_gap_k"]
        assert sliders[window]["fermi"] == start["fermi_energy_k"]


@pytest.mark.parametrize(("mode", "scattering"), EXPECTED_01)
def test_results_match_recorded_values(mode: str, scattering: str | None) -> None:
    run = next(
        run
        for run in GOLDEN["01_Fe2VAl09Si01"]["runs"]
        if run["mode"] == mode and run["scattering"] == scattering
    )
    assert run["calls"][0]["result"] == pytest.approx(EXPECTED_01[(mode, scattering)], abs=1e-3)
