import hashlib
import json
from importlib import resources
from typing import Any

import numpy as np
import pytest
from seeband_core.demo_dataset import TRUE_PARAMETERS, generate_demo_dataset, load_demo_dataset
from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitMode, FitRequest
from seeband_core.model_scales import default_start

STORED_SHA256 = "807eec98f5ba22678ca5ab8881e499483a72de7ce7d4c8c7ba8270d6383b6b84"
# Set from fits on one Mac and in Linux CI, as docs/demo-dataset.md gives.
RECOVERY_MARGIN = {
    "m_eff": 0.01,
    "band_gap": 0.005,
    "fermi_energy": 0.005,
    "A": 0.005,
    "B": 0.01,
    "m1": 0.005,
}


def combinations() -> list[tuple[str, FitMode, str | None]]:
    found: list[tuple[str, FitMode, str | None]] = []
    for description in registry.descriptions():
        for fit_mode in description.fit_modes:
            options: tuple[str | None, ...] = fit_mode.scattering or (None,)
            found += [(description.id, fit_mode, scattering) for scattering in options]
    return found


def stored_document() -> dict[str, Any]:
    path = resources.files("seeband_core") / "data" / "demo_dataset.json"
    return json.loads(path.read_text(encoding="utf-8"))


def fit(model_id: str, fit_mode: FitMode, scattering: str | None) -> Any:
    measurements = load_demo_dataset().measurements
    data = {quantity: measurements[quantity] for quantity in fit_mode.quantities}
    return registry.get(model_id).fit(
        FitRequest(fit_mode.id, data, default_start(fit_mode), scattering=scattering)
    )


def test_the_same_data_come_on_every_load() -> None:
    path = resources.files("seeband_core") / "data" / "demo_dataset.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == STORED_SHA256
    first, second = load_demo_dataset(), load_demo_dataset()
    for quantity, measurement in first.measurements.items():
        assert np.array_equal(measurement.values, second.measurements[quantity].values)


@pytest.mark.filterwarnings("ignore")
def test_the_stored_file_comes_from_the_generator() -> None:
    stored, generated = stored_document(), generate_demo_dataset()
    assert set(stored) == set(generated)
    for key, value in generated.items():
        if isinstance(value, list):
            difference = np.abs(np.array(value) - np.array(stored[key]))
            assert np.max(difference) <= 1e-9 * np.max(np.abs(stored[key])), key
        else:
            assert value == stored[key], key


@pytest.mark.filterwarnings("ignore")
def test_the_generator_gives_the_same_data_twice() -> None:
    assert generate_demo_dataset() == generate_demo_dataset()


def test_it_says_that_it_is_synthetic() -> None:
    dataset = load_demo_dataset()
    assert dataset.synthetic is True
    assert "Synthetic" in dataset.description
    assert "not a measurement" in dataset.description
    assert stored_document()["synthetic"] is True


def test_its_data_are_usable_and_in_the_units_of_the_project() -> None:
    dataset = load_demo_dataset()
    assert set(dataset.measurements) == {"seebeck", "resistivity", "hall"}
    for quantity, measurement in dataset.measurements.items():
        measurement.check(quantity)
        assert measurement.temperature_k.tolist() == np.linspace(50, 800, 31).tolist()
    # S of order 100 µV/K, and rho of order 10 µOhm m.
    seebeck = dataset.measurements["seebeck"].values
    assert 1e-4 < np.max(np.abs(seebeck)) < 5e-4
    assert 1e-6 < np.max(dataset.measurements["resistivity"].values) < 1e-3


def test_it_shows_two_bands() -> None:
    measurement = load_demo_dataset().measurements["seebeck"]
    peak = int(np.argmax(measurement.values))
    assert 100 < measurement.temperature_k[peak] < 300
    assert measurement.values[-1] < 0.5 * measurement.values[peak]
    assert measurement.values[0] < measurement.values[peak]


def test_it_has_the_stated_noise() -> None:
    document = stored_document()
    assert document["noise"]["seed"] == 2026
    assert document["true_parameters"] == dict(TRUE_PARAMETERS)


def test_it_holds_noise() -> None:
    seebeck = stored_document()["seebeck_v_per_k"]
    assert np.std(np.diff(seebeck, 2)) > 1e-7


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(
    ("model_id", "fit_mode", "scattering"),
    combinations(),
    ids=lambda value: getattr(value, "id", value),
)
def test_every_working_combination_can_fit_it(
    model_id: str, fit_mode: FitMode, scattering: str | None
) -> None:
    result = fit(model_id, fit_mode, scattering)
    # This fit fails in the disabled mode with a default start (D3).
    assert result.status == ("failed" if fit_mode.disabled else "converged")


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(
    ("fit_mode_id", "scattering", "names"),
    [
        ("dpb_s", None, ("m_eff", "band_gap", "fermi_energy")),
        ("dpb_s_rho", "acPh", ("m_eff", "band_gap", "fermi_energy", "A", "B")),
        ("dpb_s_rho_rh", "acPh", ("m_eff", "band_gap", "fermi_energy", "A", "B", "m1")),
    ],
)
def test_the_matching_modes_recover_its_parameters(
    fit_mode_id: str, scattering: str | None, names: tuple[str, ...]
) -> None:
    fit_mode = registry.get("dpb").describe().fit_mode(fit_mode_id)
    result = fit("dpb", fit_mode, scattering)
    assert result.status == "converged"
    assert result.at_bounds == ()
    for name in names:
        truth = TRUE_PARAMETERS[name]
        assert abs(result.parameters[name] - truth) <= RECOVERY_MARGIN[name] * abs(truth), name


@pytest.mark.filterwarnings("ignore")
def test_a_wrong_scattering_type_does_not_recover_it() -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho")
    result = fit("dpb", fit_mode, "dis")
    assert abs(result.parameters["m_eff"] - TRUE_PARAMETERS["m_eff"]) > 0.1
    assert "G" in result.at_bounds


@pytest.mark.filterwarnings("ignore")
def test_one_band_cannot_describe_it() -> None:
    fit_mode = registry.get("spb").describe().fit_mode("spb_s")
    assert fit("spb", fit_mode, None).at_bounds == ("fermi_energy",)
