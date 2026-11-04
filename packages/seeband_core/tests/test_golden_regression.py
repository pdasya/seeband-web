"""Replay every call recorded from the desktop window through the ported modules.

Golden results use Python 3.11, numpy 1.26 and scipy 1.17, and the project uses newer versions,
so numbers can differ slightly. On those versions, stable calls differ by at most 3.4e-6, so
RELATIVE_TOLERANCE allows about 3 times that. A formula change is far larger than this.

Some fits are not reproducible across versions, because the data do not determine their result.
They are listed in UNSTABLE and compared only on the parts that are stable. See
docs/golden-results.md.
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
RELATIVE_TOLERANCE = 1e-5
# Values this small only happen when a result is exactly or almost exactly zero.
ZERO_FLOOR = 1e-30
# Number of leading arguments that are measurement arrays in each fit function.
ARRAY_ARGUMENTS = {
    "spb_see_fit": 2,
    "spb_see_res_fit": 4,
    "dpb_see_fit": 2,
    "dpb_see_res_fit": 4,
    "dpb_see_res_hall_fit": 6,
}
# On 02_SiP no net matches, m_eff collapses towards 0, and rho then barely depends on the
# scattering parameters. Band gap and E_F stay stable, so these results keep them and the bounds.
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


def recorded_calls() -> Iterator[tuple[str, str, str | None, str, dict[str, Any]]]:
    for example in EXAMPLES:
        document = json.loads((GOLDEN / f"{example}.json").read_text(encoding="utf-8"))
        for run in document["runs"]:
            for call in run["calls"]:
                yield example, run["mode"], run["scattering"], "thread", call
            for call in run["manual_curve_calls"]:
                yield example, run["mode"], run["scattering"], "slider", call
        for call in document["d1_with_g_minimum_1"]["calls"]:
            yield example, "d1", "dis", "thread", call


CALLS = list(recorded_calls())
CALL_IDS = [
    f"{example}-{mode}-{scattering}-{source}-{call['function']}"
    for example, mode, scattering, source, call in CALLS
]


def replay(call: dict[str, Any]) -> Any:
    # Fit functions change the lists they receive, so each call gets its own copy.
    args = json.loads(json.dumps(call["args"]))
    arrays = ARRAY_ARGUMENTS.get(call["function"], 0)
    args = [np.array(value) if index < arrays else value for index, value in enumerate(args)]
    kwargs = json.loads(json.dumps(call["kwargs"]))
    method = getattr(fit_module.PB_fit(), call["function"])
    with contextlib.redirect_stdout(io.StringIO()):
        return method(*args, **kwargs)


def flat(value: Any) -> Iterator[float]:
    if isinstance(value, list | tuple):
        for item in value:
            yield from flat(item)
    elif hasattr(value, "tolist"):
        yield from flat(value.tolist())
    else:
        yield float(value)


def assert_close(actual: Any, expected: Any, tolerance: float = RELATIVE_TOLERANCE) -> None:
    got, recorded = list(flat(actual)), list(flat(expected))
    assert len(got) == len(recorded)
    for index, (x, y) in enumerate(zip(got, recorded, strict=True)):
        if math.isnan(y):
            assert math.isnan(x), f"value {index}: {x} instead of NaN"
        else:
            assert abs(x - y) <= tolerance * max(abs(y), ZERO_FLOOR), f"value {index}: {x} vs {y}"


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
        assert str(caught.value) == message
        return

    result = replay(call)
    is_fit = call["function"].endswith("_fit")
    if is_fit and example == "02_SiP" and (mode, scattering) in UNSTABLE_02:
        values, recorded = list(flat(result)), list(flat(call["result"]))
        assert len(values) == len(recorded)
        assert abs(values[0]) < COLLAPSED_M_EFF
        assert_close(values[1:3], recorded[1:3])
        return
    if is_fit and example == "01_Fe2VAl09Si01" and mode == "d1":
        assert_close(result, call["result"], D1_01_TOLERANCE)
        return
    assert_close(result, call["result"])


def test_every_recorded_call_is_replayed() -> None:
    assert len(CALLS) == 195


def test_unstable_list_only_holds_cases_that_exist() -> None:
    found = {(mode, scattering) for example, mode, scattering, _, _ in CALLS if example == "02_SiP"}
    assert UNSTABLE_02 <= found
