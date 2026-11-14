"""P5 stop-rule regressions; controlled stages isolate convergence from solver noise."""

import numpy as np
import pytest
from seeband_core import fit_module
from seeband_core.fit_module import FitProgress, PB_fit


@pytest.mark.parametrize("hall", [False, True])
@pytest.mark.parametrize("moving", ["bands", "CD"])
def test_mixed_scattering_requires_both_groups(monkeypatch, hall, moving):
    progress, stages = controlled_fit(monkeypatch, hall, moving)
    assert progress.iterations == 2
    assert not progress.reached_iteration_limit
    assert stages.count("res") == 2


def controlled_fit(monkeypatch, hall, moving, *, zero=False, zero_parameter=None, limit=4):
    stages = []
    bands = np.array([1.0, 0.0 if zero else 100.0, 0.0 if zero else 100.0])
    scatter = np.array([0.0 if zero else 1.0, 1.0, 600.0, 150.0])
    if zero_parameter is not None:
        if zero_parameter < 3:
            bands[zero_parameter] = 0.0
        else:
            scatter[zero_parameter - 3] = 0.0

    def solve(progress, stage, *args, **kwargs):
        stages.append(stage)
        if stage == "see":
            result = bands.copy()
            if moving == "bands":
                result[1] += 50
            elif moving == "nan":
                result[1] = np.nan
            elif isinstance(moving, int) and moving < 3:
                result[moving] += 50
        elif stage == "res":
            result = scatter.copy()
            if moving == "CD":
                result[2:] *= 2
            elif isinstance(moving, int) and moving >= 3:
                result[moving - 3] += 50
        else:
            result = np.array([1.0])
        return result, np.eye(len(result))

    monkeypatch.setattr(fit_module, "_curve_fit", solve)
    monkeypatch.setattr(
        fit_module.te, "dpb_fermiInt_vs_temp", lambda **kwargs: (np.ones(2), np.ones(2))
    )
    monkeypatch.setattr(fit_module.te, "dpb_rho_vs_temp_acPh_dis", lambda *args: np.ones(2))
    progress = FitProgress()
    data = [np.array([100.0, 200.0]), np.ones(2)] * (3 if hall else 2)
    args = [
        *data,
        bands.tolist(),
        ([-1000.0] * 3, [1000.0] * 3),
        [scatter[0], scatter[1], scatter[2] / 300.0, scatter[3] / 300.0, 1.0, 1.0],
        ([-1000.0] * 6, [1000.0] * 6),
    ]
    if hall:
        args += [1.0, ([0.01], [10.0])]
    function = PB_fit().dpb_see_res_hall_fit if hall else PB_fit().dpb_see_res_fit
    with np.errstate(all="raise"):
        function(*args, 1.0, "acPhDis", 0.01, limit, progress=progress)
    return progress, stages


@pytest.mark.parametrize("hall", [False, True])
def test_zero_initials_do_not_divide_by_zero(monkeypatch, hall):
    progress, _ = controlled_fit(monkeypatch, hall, "bands", zero=True)
    assert progress.iterations == 2


@pytest.mark.parametrize("hall", [False, True])
def test_limit_keeps_extra_seebeck_and_hall_stage(monkeypatch, hall):
    progress, stages = controlled_fit(monkeypatch, hall, "CD", limit=1)
    assert progress.iterations == 1
    assert progress.reached_iteration_limit
    assert stages == ["see", "res", "see"] + (["hall"] if hall else [])


@pytest.mark.parametrize("error", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_error_never_converges(error):
    assert not PB_fit().is_accuracy_reached(0.01, 0.0, error)


def test_threshold_equality_preserves_existing_rule():
    assert PB_fit().is_accuracy_reached(0.01, 0.01, 0.0)
    assert not PB_fit().is_accuracy_reached(0.01, 0.0100001)


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, float("inf")),
        (-1.0, 0.0, float("inf")),
        (3.0, 2.0, 0.5),
        (-3.0, -2.0, 0.5),
        (1.0, -2.0, 1.5),
        (float("nan"), 1.0, float("inf")),
        (1.0, float("nan"), float("inf")),
        (float("inf"), 1.0, float("inf")),
        (1.0, float("inf"), float("inf")),
        (-float("inf"), 1.0, float("inf")),
        (1.0, -float("inf"), float("inf")),
        (1e308, -1e308, float("inf")),
        (1.0, 1e-320, float("inf")),
    ],
)
def test_safe_relative_change(current, previous, expected):
    with np.errstate(all="raise"):
        change = fit_module._relative_change(current, previous)
    assert change == expected
    if not np.isfinite(expected):
        assert not PB_fit().is_accuracy_reached(1e308, change)


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("hall", [False, True])
def test_example03_needs_another_iteration_after_C2_Dhalf(hall):
    import copy
    import json
    from pathlib import Path

    document = json.loads((Path(__file__).parent / "fixtures/golden/03_AWI32_SI.json").read_text())
    mode = "dpb_s_rho_rh" if hall else "dpb_s_rho"
    run = next(r for r in document["runs"] if r["mode"] == mode and r["scattering"] == "acPhDis")
    call = copy.deepcopy(run["calls"][0])
    args = call["args"][: 16 if hall else 12]
    for index in range(6 if hall else 4):
        args[index] = np.array(args[index])
    history = []
    progress = FitProgress(on_iteration=lambda i, p: history.append(p))
    result = getattr(PB_fit(), call["function"])(*args, progress=progress)
    assert progress.iterations == 3
    assert not progress.reached_iteration_limit
    first, second, third = map(np.array, history)
    threshold = args[-2]
    assert np.allclose(second[5:7], [2.0, 0.5], rtol=1e-9)
    assert np.all(np.abs((second[5:7] - first[5:7]) / first[5:7]) <= threshold)
    assert np.max(np.abs((second[:5] - first[:5]) / first[:5])) > threshold
    assert np.all(np.abs((third[:7] - second[:7]) / second[:7]) <= threshold)
    assert np.allclose(result[:7], third[:7], rtol=1e-12)


@pytest.mark.parametrize("hall", [False, True])
@pytest.mark.parametrize("parameter", range(7), ids=["mass", "gap", "EF", "A", "B", "C", "D"])
def test_each_zero_initial_must_settle_after_becoming_nonzero(monkeypatch, hall, parameter):
    progress, _ = controlled_fit(monkeypatch, hall, parameter, zero_parameter=parameter)
    assert progress.iterations == 2
    assert not progress.reached_iteration_limit


@pytest.mark.parametrize("hall", [False, True])
def test_a_parameter_that_is_not_finite_ends_the_fit_at_once(monkeypatch, hall):
    # It cannot settle, so the loop must not run to its budget of 1000 solver rounds.
    with pytest.raises(ValueError, match="not finite"):
        controlled_fit(monkeypatch, hall, "nan", limit=1000)


def test_a_parameter_that_is_not_finite_fails_the_fit_with_its_reason():
    from seeband_core.band_models import _failure_message

    message = _failure_message(ValueError("A fitted parameter is not finite."))

    assert message == "The model gave values that are not finite during the fit."


def _example03_inv4_args(hall):
    """Example 03 in DPB acPhDis from C = 2, D = 0.5, the start #84 cites (INV-4)."""
    import copy
    import json
    from pathlib import Path

    document = json.loads((Path(__file__).parent / "fixtures/golden/03_AWI32_SI.json").read_text())
    mode = "dpb_s_rho_rh" if hall else "dpb_s_rho"
    run = next(r for r in document["runs"] if r["mode"] == mode and r["scattering"] == "acPhDis")
    call = copy.deepcopy(run["calls"][0])
    data = 6 if hall else 4
    args = call["args"][: 16 if hall else 12]
    for index in range(data):
        args[index] = np.array(args[index])
    scattering = list(args[data + 2])
    scattering[2:4] = [2.0, 0.5]
    args[data + 2] = scattering
    return call["function"], args


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("hall", [False, True])
def test_example03_from_C2_Dhalf_reaches_the_p11_regression_fixed_point(hall):
    # The independently checked P5 values describe the old S formula. Compare this
    # alternative start with the separately recorded P11 regression, not that old fixed point.
    import json
    from pathlib import Path

    mode = "dpb_s_rho_rh" if hall else "dpb_s_rho"
    document = json.loads((Path(__file__).parent / "fixtures/physics/p11.json").read_text())
    expected = next(
        value["parameters"]
        for key, value in document["results"].items()
        if key.startswith(f"03_AWI32_SI-{mode}-acPhDis-thread-")
    )
    function, args = _example03_inv4_args(hall)
    progress = FitProgress()

    result = getattr(PB_fit(), function)(*args, progress=progress)

    assert progress.iterations == 2
    assert not progress.reached_iteration_limit
    np.testing.assert_allclose(
        [result[0], result[1], result[2], result[3]],
        [expected[name] for name in ("m_eff", "band_gap", "fermi_energy", "A")],
        rtol=1e-5,
    )
    np.testing.assert_allclose(result[4:7], [1.1, 2.0, 0.5], rtol=1e-9)


@pytest.mark.filterwarnings("ignore")
def test_a_start_at_fermi_energy_0_is_no_longer_a_solver_fixed_point():
    """P8 removes the artificial zero-start fixed point, without asserting fit credibility."""
    from seeband_core.demo_dataset import load_demo_dataset
    from seeband_core.model_catalog import registry
    from seeband_core.model_interface import FitRequest
    from seeband_core.model_scales import default_start

    model = registry.get("dpb")
    mode = model.describe().fit_mode("dpb_s_rho")
    start = default_start(mode) | {"fermi_energy": 0.0}
    data = load_demo_dataset().measurements

    result = model.fit(
        FitRequest(mode.id, {q: data[q] for q in mode.quantities}, start, scattering="acPh")
    )

    assert result.status == "converged"
    assert result.iterations is not None and result.iterations > 0
    assert any(
        abs(result.parameters[name] - start[name]) > 1e-6
        for name in ("m_eff", "band_gap", "fermi_energy")
    )
