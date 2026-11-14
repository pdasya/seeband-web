import hashlib
import json
from importlib import resources
from typing import Any

import numpy as np
import pytest
from seeband_core.data_parser import parse_table
from seeband_core.demo_dataset import (
    TRUE_PARAMETERS,
    clean_curves,
    demo_table_text,
    generate_demo_dataset,
    load_demo_dataset,
)
from seeband_core.fit_quality import curve_rmse
from seeband_core.known_issues import KNOWN_ISSUES
from seeband_core.model_catalog import registry
from seeband_core.model_interface import FitMode, FitRequest
from seeband_core.model_scales import default_start

STORED_SHA256 = "d79e602fb241711e1398668fb84f65ca64c9c7145b01b42d4cbe8f761eac61a3"
# These hold for the stored data, with this noise. Another seed can miss them: see
# docs/demo-dataset.md.
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
    start = default_start(fit_mode)
    if fit_mode.id == "spb_s_rho_rh":
        # The demo's S and R_H are above 0, holes, so the SPB Hall fit starts on the hole branch,
        # as the app's automatic SPB sign does (D28). The default electron mass is refused.
        start |= {"band_mass": -1.0, "fermi_energy": -100.0}
    return registry.get(model_id).fit(FitRequest(fit_mode.id, data, start, scattering=scattering))


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
        if key != "known_issues" and isinstance(value, list):
            difference = np.abs(np.array(value) - np.array(stored[key]))
            assert np.max(difference) <= 1e-9 * np.max(np.abs(stored[key])), key
        else:
            assert value == stored[key], key


@pytest.mark.filterwarnings("ignore")
def test_the_generator_gives_the_same_data_twice() -> None:
    assert generate_demo_dataset() == generate_demo_dataset()


def test_its_text_reads_back_exactly_through_the_parser() -> None:
    dataset = load_demo_dataset()

    table = parse_table(demo_table_text(dataset))

    assert table.errors == ()
    assert table.warnings == ()
    assert set(table.measurements) == set(dataset.measurements)
    for quantity, measurement in dataset.measurements.items():
        assert np.array_equal(table.measurements[quantity].temperature_k, measurement.temperature_k)
        assert np.array_equal(table.measurements[quantity].values, measurement.values)


def test_it_says_that_it_is_synthetic_through_i18n() -> None:
    dataset = load_demo_dataset()
    assert dataset.synthetic is True
    assert stored_document()["synthetic"] is True
    assert dataset.message_key == "demo_dataset.synthetic"
    assert "description" not in stored_document()


def test_it_is_what_it_says_it_is() -> None:
    dataset = load_demo_dataset()
    assert (dataset.model, dataset.fit_mode, dataset.scattering) == ("dpb", "dpb_s_rho_rh", "acPh")
    assert dict(dataset.true_parameters) == {
        "m_eff": 1.2,
        "band_gap": 800.0,
        "fermi_energy": -150.0,
        "A": 60000.0,
        "B": 1.0,
        "m1": 1.4,
    }
    assert dataset.noise == {
        "seed": 2026,
        "seebeck_v_per_k": 1e-6,
        "resistivity_relative": 0.005,
        "hall_relative": 0.005,
    }
    registry.get(dataset.model).describe().fit_mode(dataset.fit_mode).parameters_for(
        dataset.scattering
    )


def test_it_lists_the_known_errors_of_its_data() -> None:
    dataset = load_demo_dataset()
    assert dataset.known_issues == ()
    assert set(dataset.known_issues) <= {issue.id for issue in KNOWN_ISSUES}


def test_loads_share_no_arrays() -> None:
    measurements = load_demo_dataset().measurements
    assert not np.shares_memory(
        measurements["seebeck"].temperature_k, measurements["hall"].temperature_k
    )


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


@pytest.mark.filterwarnings("ignore")
def test_it_holds_the_stated_noise() -> None:
    dataset = load_demo_dataset()
    _, clean = clean_curves()
    seebeck = dataset.measurements["seebeck"].values - clean["seebeck"]
    assert 0.5e-6 < np.std(seebeck) < 1.5e-6
    for quantity in ("resistivity", "hall"):
        relative = dataset.measurements[quantity].values / clean[quantity] - 1  # type: ignore[index]
        assert 0.0025 < np.std(relative) < 0.0075, quantity
        # Relative at both ends, not a share of the peak.
        assert np.max(np.abs(relative[-10:])) < 0.02, quantity


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
def test_the_default_spb_s_start_has_the_wrong_sign_for_it() -> None:
    fit_mode = registry.get("spb").describe().fit_mode("spb_s")
    result = fit("spb", fit_mode, None)
    assert result.at_bounds == ("fermi_energy",)
    assert result.parameters["band_mass"] > 0


@pytest.mark.filterwarnings("ignore")
def test_one_band_cannot_describe_it() -> None:
    model = registry.get("spb")
    measurements = load_demo_dataset().measurements
    data = {"seebeck": measurements["seebeck"]}
    start = {"band_mass": -1.0, "fermi_energy": -100.0}
    result = model.fit(FitRequest("spb_s", data, start))
    assert result.status == "converged"
    assert result.at_bounds == ()
    value = curve_rmse(model, "spb_s", result.parameters, data)["seebeck"].value
    assert value is not None
    assert value > 50


@pytest.mark.filterwarnings("ignore")
def test_the_matching_fit_leaves_only_the_noise() -> None:
    fit_mode = registry.get("dpb").describe().fit_mode("dpb_s_rho_rh")
    result = fit("dpb", fit_mode, "acPh")
    measurements = load_demo_dataset().measurements
    rmse = curve_rmse(registry.get("dpb"), "dpb_s_rho_rh", result.parameters, measurements, "acPh")
    assert rmse["seebeck"].value is not None
    assert rmse["seebeck"].value < 1.5
    assert rmse["resistivity"].value is not None
    assert rmse["resistivity"].value < 1.0
