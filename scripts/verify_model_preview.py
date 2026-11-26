"""Replay #259 against a running SeeBand API using its advertised models and modes."""

import argparse
import json
import sys
from math import isfinite
from urllib.request import Request, urlopen

CURVE = {"seebeck": "seebeck_v_per_k", "resistivity": "resistivity_ohm_m", "hall": "hall_m3_per_c"}


def verify(base_url: str) -> None:
    def call(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(base_url.rstrip("/") + path, data, {"Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    count = 0
    for model in call("/api/models")["models"]:
        if model["id"] not in ("spb", "dpb"):
            continue
        for mode in model["fit_modes"]:
            if mode["disabled"]:
                continue
            for law in mode["scattering"]:
                parameters = {p["name"]: p["core_range"]["default"] for p in mode["parameters"]}
                body = dict(
                    model=model["id"],
                    fit_mode=mode["id"],
                    scattering=law,
                    min_temperature_k=100,
                    max_temperature_k=700,
                    points=7,
                    parameters=parameters,
                )
                first = call("/api/calc", body)
                if model["id"] == "spb":
                    parameters["fermi_energy"] *= -1
                    parameters["band_mass"] *= -1
                else:
                    parameters["m_eff"] *= 2
                updated = call("/api/calc", body)
                keys = {CURVE[q] for q in mode["quantities"]}
                assert set(updated["curves"]) == keys and not updated["rmse"], body
                observations = {}
                for quantity in mode["quantities"]:
                    key = CURVE[quantity]
                    old, new = first["curves"][key], updated["curves"][key]
                    assert all(v is not None and isfinite(v) for v in old + new), (body, key)
                    if model["id"] == "dpb":
                        assert old != new, (body, key)
                    elif quantity in ("seebeck", "hall"):
                        assert all(x * y < 0 for x, y in zip(old, new, strict=True)), (body, key)
                    observations[quantity] = {
                        "temperature_k": updated["temperature_k"][::3],
                        "values": [v * 1.05 for v in new[::3]],
                    }
                loaded = call("/api/calc", body | {"measurements": observations})
                removed = call("/api/calc", body)
                for result in (loaded, removed):
                    assert result["temperature_k"] == updated["temperature_k"], body
                    assert result["curves"] == updated["curves"], body
                assert set(loaded["rmse"]) == set(mode["quantities"]), body
                assert all(isfinite(item["value"]) for item in loaded["rmse"].values()), body
                assert removed["rmse"] == {}, body
                count += 1
                sys.stdout.write(f"{mode['id']} {law} OK\n")
    assert count > 0, "The API advertised no supported combinations"
    sys.stdout.write(f"Verified {count} model, fit-mode and scattering combinations.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    verify(parser.parse_args().base_url)
