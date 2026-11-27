# ruff: noqa: T201 -- print replay results for reviewers.
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from seeband_api.main import create_app

f = Path(__file__).with_name("export.txt")
rows = np.loadtxt([line for line in f.read_text().splitlines() if line and line[0].isdigit()])
data = {
    "model": "dpb",
    "fit_mode": "dpb_s_rho_rh",
    "scattering": "acPh",
    "min_temperature_k": 50,
    "max_temperature_k": 800,
    "points": 50,
    "parameters": {
        "F": 1000,
        "G": 1,
        "m_eff": 1.19429880474,
        "band_gap": 0.0688736950017 / 8.617333262e-5,
        "fermi_energy": -0.012940397676 / 8.617333262e-5,
        "A": 59915.0350422,
        "B": 0.991892578249,
        "m1": 1.40069265081,
    },
}


def calc(kind):
    with TestClient(create_app()) as client:
        response = client.post("/api/calc", json=dict(data, kind=kind))
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    l = calc("lorenz_number")  # noqa: E741
    print("temperature deviation", np.max(abs(rows[:, 0] - l["temperature_k"])))
    for i, name in enumerate(
        [
            "lorenz_number_w_ohm_per_k2",
            "lorenz_number_band_1_w_ohm_per_k2",
            "lorenz_number_band_2_w_ohm_per_k2",
        ]
    ):
        rel = np.max(abs(np.array(l["curves"][name]) / rows[:, 1 + 2 * i] - 1))
        print(name, rel)
        assert rel < 1e-9
    k = calc("thermal_conductivity")["curves"]["thermal_conductivity_w_per_m_k"]
    sig = calc("electrical_conductivity")["curves"]["electrical_conductivity_s_per_m"]
    rel = np.max(
        abs(
            np.array(k)
            / (
                np.array(sig)
                * np.array(l["temperature_k"])
                * l["curves"]["lorenz_number_w_ohm_per_k2"]
            )
            - 1
        )
    )
    print("kappa_e identity", rel)
    assert rel < 1e-12
