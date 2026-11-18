"""R7: how a fit found each parameter, from the signals it has, and no green "fitted" for all."""

import logging

import numpy as np
import pytest
from seeband_core.demo_dataset import load_demo_dataset
from seeband_core.model_catalog import registry
from seeband_core.model_interface import (
    Bounds,
    CurveRequest,
    FitRequest,
    FitStopped,
    Measurement,
)
from seeband_core.model_scales import default_start
from seeband_core.parameter_status import DID_NOT_MOVE_TOLERANCE, parameter_statuses

DEMO = load_demo_dataset().measurements
ALGORITHMS = ("legacy-sequential-v1", "verified-sequential-v2")


def _fit(model_id: str, mode_id: str, **fields: object) -> object:
    model = registry.get(model_id)
    fit_mode = model.describe().fit_mode(mode_id)
    start = fields.pop("start", default_start(fit_mode))
    on_iteration = fields.pop("on_iteration", None)
    request = FitRequest(
        mode_id,
        {quantity: DEMO[quantity] for quantity in fit_mode.quantities},
        start,  # type: ignore[arg-type]
        **fields,  # type: ignore[arg-type]
    )
    return model.fit(request, on_iteration)  # type: ignore[arg-type]


@pytest.mark.parametrize("mode_id", ["dpb_s", "dpb_s_rho", "dpb_s_rho_rh"])
@pytest.mark.parametrize("scattering", ["acPh", "dis", "ionized"])
def test_dpb_curves_do_not_depend_on_a_fermi_energy_inside_the_gap(
    mode_id: str, scattering: str
) -> None:
    """The zero-temperature carrier populations vanish for every E_F in the gap."""
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode(mode_id)
    start = default_start(fit_mode) | {"m_eff": 1.2, "band_gap": 800.0}

    def curves(fermi_energy: float, *, in_gap: bool) -> dict[str, bytes]:
        result = model.calculate(
            CurveRequest(
                mode_id,
                start | {"fermi_energy": fermi_energy},
                100.0,
                800.0,
                12,
                scattering,
            )
        )
        assert ("fermi_energy_in_gap" in result.known_issues) is in_gap
        return {name: np.asarray(values).tobytes() for name, values in result.curves.items()}

    reference = curves(400.0, in_gap=True)
    for energy in (0.0, 50.0, 790.0, 800.0):
        assert curves(energy, in_gap=True) == reference
    assert curves(810.0, in_gap=False) != reference


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(("mode_id", "scattering"), [("dpb_s", None), ("dpb_s_rho", "acPh")])
def test_a_fermi_energy_inside_the_gap_is_not_determined(
    mode_id: str, scattering: str | None, algorithm: str
) -> None:
    """The review's s13 cases: E_F in the gap with m_eff > 0 has no effect on the data.

    The legacy fit ends with E_F where it started, which says nothing about it. The verified fit
    finds no derivative to verify and fails, so it assesses E_F not at all. Neither calls it
    estimated.
    """
    fit_mode = registry.get("dpb").describe().fit_mode(mode_id)
    start = default_start(fit_mode) | {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 400.0}
    held = frozenset(name for name in ("m_eff", "band_gap", "A", "B") if name in start)

    result = _fit(
        "dpb", mode_id, start=start, scattering=scattering, algorithm=algorithm, held=held
    )

    status = result.parameter_status["fermi_energy"]  # type: ignore[attr-defined]
    if algorithm == "legacy-sequential-v1":
        assert result.status != "failed"  # type: ignore[attr-defined]
        assert 0 < result.parameters["fermi_energy"] < 800.0  # type: ignore[attr-defined]
        assert status == "not_determined"
        assert "fermi_energy_in_gap" in result.known_issues  # type: ignore[attr-defined]
    else:
        assert result.status == "failed"  # type: ignore[attr-defined]
        assert status == "not_assessed"


def test_verified_fit_warns_about_fermi_energy_for_an_exact_in_gap_curve() -> None:
    model = registry.get("dpb")
    mode = model.describe().fit_mode("dpb_s")
    start = default_start(mode) | {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 400.0}
    curve = model.calculate(CurveRequest(mode.id, start, 100, 800, 12, "acPh"))
    data = Measurement(curve.temperature_k, curve.curves["seebeck_v_per_k"])

    result = model.fit(
        FitRequest(
            mode.id,
            {"seebeck": data},
            start,
            scattering="acPh",
            held=frozenset({"m_eff", "band_gap"}),
        )
    )

    assert result.status == "converged"
    assert result.parameters["fermi_energy"] == 400.0
    assert result.parameter_status["fermi_energy"] == "not_determined"
    assert "fermi_energy_in_gap" in result.known_issues


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_a_stopped_fit_marks_a_parameter_at_its_bound(algorithm: str) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho")
    start = default_start(fit_mode)

    def stop(_: object) -> None:
        raise FitStopped

    result = _fit(
        "dpb",
        "dpb_s_rho",
        start=start,
        bounds={"B": Bounds(start["B"] * 0.999, start["B"] * 1.0001)},
        scattering="acPh",
        algorithm=algorithm,
        on_iteration=stop,
    )

    assert result.status == "stopped"  # type: ignore[attr-defined]
    assert "B" in result.at_bounds  # type: ignore[attr-defined]
    assert result.parameter_status["B"] == "at_bound"  # type: ignore[attr-defined]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_held_fixed_and_fitted_parameters_each_have_a_status(algorithm: str) -> None:
    result = _fit("dpb", "dpb_s_rho", scattering="acPh", algorithm=algorithm, held={"B"})
    statuses = result.parameter_status  # type: ignore[attr-defined]
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho")

    assert set(statuses) == set(result.parameters)  # type: ignore[attr-defined]
    assert statuses["B"] == "held"
    for spec in fit_mode.parameters:
        if spec.role == "fixed" or "acPh" not in (spec.scattering or ("acPh",)):
            assert statuses[spec.name] == "fixed"
    assert statuses["m_eff"] == "estimated"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_a_failed_fit_assesses_no_parameter(
    algorithm: str, caplog: pytest.LogCaptureFixture
) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    # The start band mass has the wrong sign for E_F above both bands, so no root exists.
    start = default_start(fit_mode) | {"m_eff": -1.0, "band_gap": 100.0, "fermi_energy": 500.0}

    with caplog.at_level(logging.CRITICAL):
        result = _fit("dpb", "dpb_s", start=start, algorithm=algorithm)

    assert result.status == "failed"  # type: ignore[attr-defined]
    fitted = {spec.name for spec in fit_mode.parameters if spec.role == "fitted"}
    assert {
        name: status
        for name, status in result.parameter_status.items()  # type: ignore[attr-defined]
        if name in fitted
    } == dict.fromkeys(fitted, "not_assessed")


def test_a_stopped_hall_fit_does_not_assess_m1() -> None:
    def stop(_: object) -> None:
        raise FitStopped

    result = _fit(
        "dpb",
        "dpb_s_rho_rh",
        scattering="acPh",
        algorithm="legacy-sequential-v1",
        on_iteration=stop,
    )

    assert result.status == "stopped"  # type: ignore[attr-defined]
    assert result.parameter_status["m1"] == "not_assessed"  # type: ignore[attr-defined]


def _statuses(parameters: dict[str, float], **signals: object) -> dict[str, str]:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s")
    start = {"m_eff": 1.2, "band_gap": 800.0, "fermi_energy": 900.0}
    return dict(
        parameter_statuses(
            fit_mode,
            None,
            start,
            start | parameters,
            status=signals.pop("status", "converged"),  # type: ignore[arg-type]
            held=signals.pop("held", ()),  # type: ignore[arg-type]
            at_bounds=signals.pop("at_bounds", ()),  # type: ignore[arg-type]
            undetermined=signals.pop("undetermined", ()),  # type: ignore[arg-type]
            reached=signals.pop("reached", None),  # type: ignore[arg-type]
            points=signals.pop("points", {"seebeck": 30}),  # type: ignore[arg-type]
            unassessed=signals.pop("unassessed", ()),  # type: ignore[arg-type]
        )
    )


def test_each_signal_gives_its_status_in_order() -> None:
    moved = {"m_eff": 1.5, "band_gap": 700.0, "fermi_energy": 950.0}
    assert _statuses(moved) == dict.fromkeys(moved, "estimated")
    assert _statuses(moved, undetermined={"m_eff"})["m_eff"] == "not_determined"
    # A bound is said first, as it may be what set the value.
    assert _statuses(moved, undetermined={"m_eff"}, at_bounds={"m_eff"})["m_eff"] == "at_bound"
    assert _statuses(moved, reached={"m_eff"})["band_gap"] == "not_assessed"
    assert _statuses(moved, status="failed")["m_eff"] == "not_assessed"
    assert _statuses(moved, held={"m_eff"})["m_eff"] == "held"
    assert _statuses(moved, unassessed={"m_eff"})["m_eff"] == "not_assessed"


@pytest.mark.parametrize("status", ["stopped", "iteration_limit", "stalled"])
def test_a_fit_that_did_not_converge_calls_nothing_estimated(status: str) -> None:
    """Its values did not settle, so no sign of a problem is no sign that they are fine."""
    moved = {"m_eff": 1.5, "band_gap": 700.0, "fermi_energy": 950.0}
    statuses = _statuses(moved, status=status, at_bounds={"band_gap"})
    assert statuses == {
        "m_eff": "not_assessed",
        "band_gap": "at_bound",
        "fermi_energy": "not_assessed",
    }


def test_a_stage_with_no_spare_points_assesses_nothing() -> None:
    moved = {"m_eff": 1.5, "band_gap": 700.0, "fermi_energy": 950.0}
    assert set(_statuses(moved, points={"seebeck": 3}).values()) == {"not_assessed"}
    assert set(_statuses(moved, points={"seebeck": 4}).values()) == {"estimated"}
    # A held parameter is not one the stage fits.
    assert _statuses(moved, points={"seebeck": 3}, held={"m_eff"})["band_gap"] == "estimated"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_a_fit_through_as_many_points_as_parameters_is_not_called_undetermined(
    algorithm: str,
) -> None:
    """The review's case: three points of S from the model, which a DPB S fit passes through.

    scipy gives no covariance then, which once read as "the data do not depend on it", while the
    fit found the values exactly.
    """
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    truth = default_start(fit_mode) | {"m_eff": 1.2, "band_gap": 1500.0, "fermi_energy": -200.0}
    temperatures = np.array([200.0, 400.0, 600.0])
    curve = model.calculate(CurveRequest("dpb_s", truth, 200.0, 600.0, 3, None, "measured"))
    seebeck = np.asarray(curve.curves["seebeck_v_per_k"])
    start = truth | {"m_eff": 1.0, "band_gap": 1400.0, "fermi_energy": -150.0}
    result = model.fit(
        FitRequest(
            "dpb_s",
            {"seebeck": Measurement(temperatures, seebeck)},
            start,
            algorithm=algorithm,  # type: ignore[arg-type]
        )
    )

    fitted = {"m_eff", "band_gap", "fermi_energy"}
    assert {
        name: status for name, status in result.parameter_status.items() if name in fitted
    } == dict.fromkeys(fitted, "not_assessed")


def test_the_status_is_given_also_for_a_request_passed_by_name() -> None:
    model = registry.get("dpb")
    fit_mode = model.describe().fit_mode("dpb_s")
    request = FitRequest(
        "dpb_s",
        {"seebeck": DEMO["seebeck"]},
        default_start(fit_mode),
        algorithm="legacy-sequential-v1",
    )
    assert model.fit(request=request).parameter_status == model.fit(request).parameter_status


def test_a_value_that_stayed_at_its_start_did_not_move() -> None:
    within = 900.0 * (1 + DID_NOT_MOVE_TOLERANCE / 2)
    beyond = 900.0 * (1 + DID_NOT_MOVE_TOLERANCE * 2)
    assert _statuses({"fermi_energy": within})["fermi_energy"] == "did_not_move"
    assert _statuses({"fermi_energy": beyond})["fermi_energy"] == "estimated"


def test_only_a_dpb_fermi_energy_strictly_inside_the_gap_with_a_positive_mass() -> None:
    moved = {"m_eff": 1.5, "band_gap": 800.0}
    assert _statuses(moved | {"fermi_energy": 400.0})["fermi_energy"] == "not_determined"
    assert _statuses(moved | {"fermi_energy": 810.0})["fermi_energy"] == "estimated"
    assert _statuses(moved | {"fermi_energy": -5.0})["fermi_energy"] == "estimated"
    # Its edges too: the curves there are the same to the bit as inside.
    assert _statuses(moved | {"fermi_energy": 0.0})["fermi_energy"] == "not_determined"
    assert _statuses(moved | {"fermi_energy": 800.0})["fermi_energy"] == "not_determined"
    negative = {"m_eff": -1.5, "band_gap": 800.0, "fermi_energy": 400.0}
    assert _statuses(negative)["fermi_energy"] == "estimated"
