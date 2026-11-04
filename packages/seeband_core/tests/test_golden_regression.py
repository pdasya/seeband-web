"""Replay every call recorded from the desktop window through the ported modules.

Golden results were captured on one Mac with Python 3.11, numpy 1.26 and scipy 1.17. The project
uses newer versions, and CI runs on Linux. docs/golden-results.md gives the measured differences.

CURVE_TOLERANCE is tight, because curves are direct calculations. FIT_TOLERANCE is looser, because
fits depend on the solver. A small change can stay within FIT_TOLERANCE, but the curves catch it.

Some fits are not reproducible across versions: see UNSTABLE_02 and deviation D19.

Tests call the core only through call_core. When a refactor renames a function or drops an argument
such as print_info, update call_core and leave the pinned fixtures unchanged.
"""

import contextlib
import io
import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from seeband_core import fit_module

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
EXAMPLES = ["01_Fe2VAl09Si01", "02_SiP", "03_AWI32_SI"]
CURVE_TOLERANCE = 1e-9
FIT_TOLERANCE = 1e-5
# Number of leading arguments that are measurement arrays in each fit function.
ARRAY_ARGUMENTS = {
    "spb_see_fit": 2,
    "spb_see_res_fit": 4,
    "dpb_see_fit": 2,
    "dpb_see_res_fit": 4,
    "dpb_see_res_hall_fit": 6,
}
# Error text can change with a scipy update, so only a stable part of it is compared.
ERROR_FRAGMENTS = {"ValueError": "bounds"}
# These fits stop near their start on the recorded versions, and move further on newer ones (D19).
UNSTABLE_02 = {
    ("dpb_s", None),
    ("dpb_s_rho", "acPh"),
    ("dpb_s_rho", "dis"),
    ("dpb_s_rho", "acPhDis"),
    ("dpb_s_rho_rh", "acPh"),
    ("dpb_s_rho_rh", "acPhDis"),
    ("d1", "dis"),
}
COLLAPSED_M_EFF = 1e-5
# The G minimum case on 01 is not credible either, and differs by about 1e-4.
D1_01_TOLERANCE = 1e-3
# Public methods with no recorded call. The first is unreachable on the desktop because of D2.
NOT_COVERED = {
    "spb_see_res_hall_fit",
    "chempot_1PB",
    "chempot_2PB",
    "dpb_see_res_hall_fit_new",
    "ind_cc_2PB",
    "ind_seebeck_2PB",
    "is_accuracy_reached",
}


def recorded_calls() -> Iterator[tuple[str, str, str | None, str, dict[str, Any]]]:
    for example in EXAMPLES:
        document = json.loads((GOLDEN / f"{example}.json").read_text(encoding="utf-8"))
        for run in document["runs"]:
            for call in run["calls"]:
                yield example, run["mode"], run["scattering"], "thread", call
            for call in run["manual_curve_calls"]:
                yield example, run["mode"], run["scattering"], "slider", call
            for graph in run["graph_buttons"]:
                for call in graph["calls"]:
                    yield example, run["mode"], run["scattering"], graph["button"], call
        for call in document["d1_with_g_minimum_1"]["calls"]:
            yield example, "d1", "dis", "thread", call


CALLS = list(recorded_calls())
CALL_IDS = [
    f"{example}-{mode}-{scattering}-{source}-{call['function']}"
    for example, mode, scattering, source, call in CALLS
]


def call_core(function: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
    """Run a recorded desktop call against the core. This is the only link to its names."""
    arrays = ARRAY_ARGUMENTS.get(function, 0)
    converted = [np.array(value) if index < arrays else value for index, value in enumerate(args)]
    with contextlib.redirect_stdout(io.StringIO()):
        return getattr(fit_module.PB_fit(), function)(*converted, **kwargs)


def replay(call: dict[str, Any]) -> Any:
    # Fit functions change the lists they receive, so each call gets its own copy.
    return call_core(
        call["function"],
        json.loads(json.dumps(call["args"])),
        json.loads(json.dumps(call["kwargs"])),
    )


def flat(value: Any) -> Iterator[float]:
    if isinstance(value, list | tuple):
        for item in value:
            yield from flat(item)
    elif hasattr(value, "tolist"):
        yield from flat(value.tolist())
    else:
        yield float(value)


def assert_close(actual: Any, expected: Any, tolerance: float) -> None:
    got, recorded = list(flat(actual)), list(flat(expected))
    assert len(got) == len(recorded)
    for index, (x, y) in enumerate(zip(got, recorded, strict=True)):
        if math.isfinite(y):
            assert abs(x - y) <= tolerance * abs(y), f"value {index}: {x} vs {y}"
        else:
            assert x == y or (math.isnan(x) and math.isnan(y)), f"value {index}: {x} vs {y}"


def bounds_received(function: str, args: list[Any]) -> list[tuple[float, float]]:
    """Return the bounds of each parameter in result order, from a recorded DPB fit call."""
    arrays = ARRAY_ARGUMENTS[function]
    see = args[arrays + 1]
    pairs = list(zip(see[0], see[1], strict=True))
    if function != "dpb_see_fit":
        res = args[arrays + 3]
        pairs += list(zip(res[0], res[1], strict=True))
    if function == "dpb_see_res_hall_fit":
        pairs.append((args[arrays + 5][0][0], args[arrays + 5][1][0]))
    return pairs


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(("example", "mode", "scattering", "source", "call"), CALLS, ids=CALL_IDS)
def test_replay_matches_the_desktop(
    example: str, mode: str, scattering: str | None, source: str, call: dict[str, Any]
) -> None:
    if "error" in call:
        kind, _, message = call["error"].partition(": ")
        with pytest.raises(Exception) as caught:
            replay(call)
        assert type(caught.value).__name__ == kind
        assert ERROR_FRAGMENTS.get(kind, message) in str(caught.value)
        return

    result = replay(call)
    if not call["function"].endswith("_fit"):
        assert_close(result, call["result"], CURVE_TOLERANCE)
    elif example == "02_SiP" and (mode, scattering) in UNSTABLE_02:
        values, recorded = list(flat(result)), list(flat(call["result"]))
        assert len(values) == len(recorded)
        assert abs(values[0]) < COLLAPSED_M_EFF
        assert_close(values[1:3], recorded[1:3], FIT_TOLERANCE)
        bounds = bounds_received(call["function"], call["args"])
        fitted = [(v, b) for v, b in zip(values, bounds, strict=False)]
        for value, (lower, upper) in fitted[:3]:
            assert lower <= value <= upper
    elif example == "01_Fe2VAl09Si01" and mode == "d1":
        assert_close(result, call["result"], D1_01_TOLERANCE)
    else:
        assert_close(result, call["result"], FIT_TOLERANCE)


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("scattering", ["acPh", "acPhDis"])
def test_d19_scale_follows_the_data_on_these_versions(scattering: str) -> None:
    """On 02_SiP, the desktop result stays at its start. Newer versions match the rho data."""
    call = next(
        call
        for example, mode, s, source, call in CALLS
        if example == "02_SiP" and mode == "dpb_s_rho" and s == scattering and source == "thread"
        if call["function"] == "dpb_see_res_fit"
    )
    assert call["result"][3] == 40000.0
    parameters = replay(call)
    temperature, measured = np.array(call["args"][2]), np.array(call["args"][3])
    band, scattering_values = list(parameters[:3]), list(parameters[3:9])
    grid, _, curve = call_core(
        "dpb_see_res_calc",
        [temperature.min(), temperature.max(), 50, band, scattering_values, call["args"][8]],
        {"scatter_type": scattering},
    )
    ratio = float(np.median(measured / np.interp(temperature, grid, curve)))
    assert 0.1 < ratio < 10


def count_function_entries(node: Any) -> int:
    """Count recorded calls by another route, so a new fixture section cannot be missed."""
    if isinstance(node, dict):
        return int("function" in node) + sum(count_function_entries(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_function_entries(item) for item in node)
    return 0


def test_every_recorded_call_is_replayed() -> None:
    documents = [json.loads((GOLDEN / f"{name}.json").read_text("utf-8")) for name in EXAMPLES]
    assert len(CALLS) == sum(count_function_entries(document) for document in documents)


def test_coverage_of_public_methods_is_as_documented() -> None:
    public = {
        name
        for name in dir(fit_module.PB_fit)
        if not name.startswith("_") and callable(getattr(fit_module.PB_fit, name))
    }
    called = {call["function"] for *_, call in CALLS}
    assert public - called == NOT_COVERED


def test_unstable_list_only_holds_cases_that_exist() -> None:
    found = {(mode, scattering) for example, mode, scattering, *_ in CALLS if example == "02_SiP"}
    assert UNSTABLE_02 <= found
