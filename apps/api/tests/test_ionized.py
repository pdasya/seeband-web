"""Public ionized model paths share one mechanism through curves, residuals and fit."""

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from seeband_api.main import create_app
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest
from seeband_core.model_scales import default_start


@pytest.mark.parametrize("model_id", ["spb", "dpb"])
@pytest.mark.parametrize("suffix", ["s", "s_rho", "s_rho_rh"])
def test_ionized_fit_and_input_grid_are_consistent(model_id: str, suffix: str) -> None:
    mode_id = f"{model_id}_{suffix}"
    model = registry.get(model_id)
    mode = model.describe().fit_mode(mode_id)
    truth = default_start(mode)
    # Synthetic inputs: each endpoint is produced by the selected model, not a measurement.
    curve = model.calculate(
        CurveRequest(
            fit_mode=mode_id,
            parameters=truth,
            scattering="ionized",
            min_temperature_k=200.0,
            max_temperature_k=500.0,
            points=5,
        )
    )
    columns = {
        "seebeck": "seebeck_v_per_k",
        "resistivity": "resistivity_ohm_m",
        "hall": "hall_m3_per_c",
    }
    measurements = {
        q: {
            "temperature_k": curve.temperature_k.tolist(),
            "values": curve.curves[columns[q]].tolist(),
        }
        for q in mode.quantities
    }
    free = "fermi_energy" if suffix == "s" else "A"
    held = [p.name for p in mode.parameters_for("ionized") if p.role == "fitted" and p.name != free]
    start = truth | {free: truth[free] * 1.1}
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/fit",
            json={
                "model": model_id,
                "fit_mode": mode_id,
                "scattering": "ionized",
                "start": start,
                "held": held,
                "measurements": measurements,
                "min_temperature_k": 200.0,
                "max_temperature_k": 500.0,
                "algorithm": "verified-sequential-v2",
            },
        )
        assert response.status_code == 200
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        result = events[-1]["result"]
        assert result["algorithm"] == "verified-sequential-v2"
        assert result["status"] == "converged", result
        np.testing.assert_allclose(result["parameters"][free], truth[free], rtol=2e-4)
        residual_response = client.post(
            "/api/calc",
            json={
                "model": model_id,
                "fit_mode": mode_id,
                "scattering": "ionized",
                "parameters": result["parameters"],
                "min_temperature_k": 200.0,
                "max_temperature_k": 500.0,
                "points": 5,
                "measurements": measurements,
            },
        )
        assert residual_response.status_code == 200
        assert residual_response.json()["known_issues"] == []
        for residual in result["diagnostics"]["residuals"].values():
            assert residual["relative_l2"] < 1e-5


@pytest.mark.parametrize("model_id", ["spb", "dpb"])
def test_retired_mixed_scattering_is_not_relabelled(model_id: str) -> None:
    mode_id = f"{model_id}_s_rho"
    mode = registry.get(model_id).describe().fit_mode(mode_id)
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/calc",
            json={
                "model": model_id,
                "fit_mode": mode_id,
                "scattering": "acPhDis",
                "parameters": default_start(mode),
                "min_temperature_k": 200.0,
                "max_temperature_k": 500.0,
            },
        )
    assert response.status_code == 422
    assert any(d["code"] == "unknown_scattering" for d in response.json()["details"])


def test_spb_numerical_guess_uses_ionized_scattering() -> None:
    model = registry.get("spb")
    mode = model.describe().fit_mode("spb_s")
    truth = default_start(mode) | {"band_mass": -1.0, "fermi_energy": -700.0}
    curve = model.calculate(
        CurveRequest(
            fit_mode="spb_s",
            parameters=truth,
            scattering="ionized",
            min_temperature_k=200.0,
            max_temperature_k=500.0,
            points=8,
        )
    )
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/guess",
            json={
                "model": "spb",
                "scattering": "ionized",
                "temperature_k": curve.temperature_k.tolist(),
                "seebeck_v_per_k": curve.curves["seebeck_v_per_k"].tolist(),
            },
        )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "numerical_guess"
    assert result["start_values"]["fermi_energy"] == -700.0
    assert result["rmse_v_per_k"] < 1e-10


@pytest.mark.parametrize("model_id", ["spb", "dpb"])
def test_ionized_legacy_is_rejected_before_starting_a_fit(model_id: str) -> None:
    mode_id = f"{model_id}_s"
    mode = registry.get(model_id).describe().fit_mode(mode_id)
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/fit",
            json={
                "model": model_id,
                "fit_mode": mode_id,
                "scattering": "ionized",
                "algorithm": "legacy-sequential-v1",
                "start": default_start(mode),
                "min_temperature_k": 200.0,
                "max_temperature_k": 500.0,
                "measurements": {
                    "seebeck": {"temperature_k": [200.0, 500.0], "values": [1e-4, 2e-4]}
                },
            },
        )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_fit"
    assert any(d["code"] == "unsupported_algorithm" for d in response.json()["details"])
