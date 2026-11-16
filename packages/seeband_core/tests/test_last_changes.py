"""R8: an iterative legacy fit says how much each parameter changed when its stop rule ended it."""

import math

import pytest
from seeband_core.demo_dataset import load_demo_dataset
from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitRequest, FitResult
from seeband_core.model_scales import default_start

DEMO = load_demo_dataset().measurements


def _fit(mode_id: str, scattering: str | None, algorithm: str) -> tuple[FitResult, object]:
    model = registry.get(mode_id.partition("_")[0])
    fit_mode = model.describe().fit_mode(mode_id)
    request = FitRequest(
        mode_id,
        {quantity: DEMO[quantity] for quantity in fit_mode.quantities},
        default_start(fit_mode),
        scattering=scattering,
        algorithm=algorithm,  # type: ignore[arg-type]
    )
    return model.fit(request), fit_mode


@pytest.mark.parametrize(
    ("mode_id", "scattering", "loop"),
    [
        ("dpb_s_rho", "acPh", ["m_eff", "band_gap", "fermi_energy", "A", "B"]),
        ("dpb_s_rho", "dis", ["m_eff", "band_gap", "fermi_energy", "F", "G"]),
        ("dpb_s_rho_rh", "acPh", ["m_eff", "band_gap", "fermi_energy", "A", "B"]),
    ],
)
def test_a_converged_loop_names_each_change_and_each_is_within_its_rule(
    mode_id: str, scattering: str, loop: list[str]
) -> None:
    result, fit_mode = _fit(mode_id, scattering, "legacy-sequential-v1")

    assert result.status == "converged"
    assert list(result.last_changes) == loop
    threshold = fit_mode.threshold  # type: ignore[attr-defined]
    assert all(
        math.isfinite(change) and change <= threshold for change in result.last_changes.values()
    )


def test_the_changes_are_those_the_rule_compared(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not changes worked out again from the values, which could round otherwise."""
    from seeband_core import fit_module

    compared: list[list[float]] = []
    reached = fit_module.PB_fit.is_accuracy_reached

    def recording(self: object, threshold: float, *errors: float) -> bool:
        compared.append(list(errors))
        return reached(self, threshold, *errors)  # type: ignore[arg-type]

    monkeypatch.setattr(fit_module.PB_fit, "is_accuracy_reached", recording)
    result, _ = _fit("dpb_s_rho", "acPh", "legacy-sequential-v1")

    assert list(result.last_changes.values()) == compared[-1]


@pytest.mark.parametrize(
    ("mode_id", "scattering", "algorithm"),
    [
        ("dpb_s", None, "legacy-sequential-v1"),
        ("spb_s_rho", "acPh", "legacy-sequential-v1"),
        ("dpb_s_rho", "acPh", "verified-sequential-v2"),
    ],
)
def test_a_single_pass_or_verified_fit_has_no_loop_changes(
    mode_id: str, scattering: str | None, algorithm: str
) -> None:
    result, _ = _fit(mode_id, scattering, algorithm)
    assert result.last_changes == {}
