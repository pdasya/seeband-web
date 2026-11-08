"""End-to-end registry, process worker and streamed fit for the SKB model."""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from running_server import read_events
from seeband_api.main import create_app
from seeband_core.model_catalog import registry
from seeband_core.model_interface import CurveRequest
from seeband_core.model_scales import default_start


def test_joint_kane_fit_in_worker_and_derived_temperature_curves() -> None:
    model = registry.get("skb")
    mode = model.describe().fit_mode("skb_s_rho_rh")
    true = default_start(mode) | {"band_mass": 0.15, "fermi_energy": 400.0, "A": 20000.0}
    clean = model.calculate(CurveRequest(mode.id, true, 100, 700, 10, "acPh"))
    columns = {
        "seebeck": "seebeck_v_per_k",
        "resistivity": "resistivity_ohm_m",
        "hall": "hall_m3_per_c",
    }
    measurements = {
        q: {"temperature_k": clean.temperature_k.tolist(), "values": clean.curves[c].tolist()}
        for q, c in columns.items()
    }
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/fit",
            json={
                "model": "skb",
                "fit_mode": mode.id,
                "scattering": "acPh",
                "start": default_start(mode) | {"band_mass": 0.2, "fermi_energy": 250.0},
                "measurements": measurements,
                "min_temperature_k": 100,
                "max_temperature_k": 700,
            },
        )
        assert response.status_code == 200
        events = list(read_events(iter(response.text.splitlines())))
        assert events[-1]["type"] == "done", events
        result = events[-1]["result"]
        assert result["status"] == "converged"
        for name in ("band_mass", "fermi_energy", "A"):
            assert result["parameters"][name] == pytest.approx(true[name], rel=2e-4)
        body = {
            "model": "skb",
            "fit_mode": mode.id,
            "scattering": "acPh",
            "parameters": result["parameters"],
            "min_temperature_k": 100,
            "max_temperature_k": 700,
            "points": 12,
        }
        for kind, column in (
            ("lorenz_number", "lorenz_w_ohm_per_k2"),
            ("chemical_potential", "chemical_potential_k"),
            ("carrier_mobility", "mobility_m2_per_v_s"),
        ):
            answer = client.post("/api/calc", json=body | {"kind": kind})
            assert answer.status_code == 200, answer.text
            values = answer.json()["curves"][column]
            assert len(values) == 12
            assert np.all(np.isfinite(values))
            assert np.ptp(values) > 0
        dispersion = client.post("/api/calc", json=body | {"kind": "band_structure"})
        assert dispersion.status_code == 200
        plot = dispersion.json()
        assert plot["temperature_k"] == []
        k = plot["curves"]["wavevector_per_m"]
        energy = plot["curves"]["band_energy_ev"]
        assert k[0] < 0 < k[-1]
        assert energy[0] == pytest.approx(energy[-1])
