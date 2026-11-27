"""Replay #259 against a running SeeBand API using its advertised models and modes."""

import argparse
import json
import sys
from math import isfinite
from urllib.request import Request, urlopen

CURVE = {"seebeck": "seebeck_v_per_k", "resistivity": "resistivity_ohm_m", "hall": "hall_m3_per_c"}
# Nonzero SPB values, so that negating both flips the carrier type whatever the defaults are.
SPB_START = {"fermi_energy": 150.0, "band_mass": 1.2}


def check(condition: bool, context: object) -> None:
    """A failed check stops the replay. Unlike assert, it also runs under python -O."""
    if not condition:
        raise SystemExit(f"FAILED: {context}")


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
                if model["id"] == "spb":
                    parameters |= SPB_START
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
                changed = dict(parameters)
                if model["id"] == "spb":
                    changed["fermi_energy"] *= -1
                    changed["band_mass"] *= -1
                else:
                    changed["m_eff"] *= 2
                body = body | {"parameters": changed}
                updated = call("/api/calc", body)
                keys = {CURVE[q] for q in mode["quantities"]}
                check(set(updated["curves"]) == keys and not updated["rmse"], body)
                observations = {}
                for quantity in mode["quantities"]:
                    key = CURVE[quantity]
                    old, new = first["curves"][key], updated["curves"][key]
                    check(all(v is not None and isfinite(v) for v in old + new), (body, key))
                    if model["id"] == "dpb":
                        check(old != new, (body, key))
                    elif quantity in ("seebeck", "hall"):
                        check(all(x * y < 0 for x, y in zip(old, new, strict=True)), (body, key))
                    observations[quantity] = {
                        "temperature_k": updated["temperature_k"][::3],
                        "values": [v * 1.05 for v in new[::3]],
                    }
                loaded = call("/api/calc", body | {"measurements": observations})
                removed = call("/api/calc", body)
                for result in (loaded, removed):
                    check(result["temperature_k"] == updated["temperature_k"], body)
                    check(result["curves"] == updated["curves"], body)
                check(set(loaded["rmse"]) == set(mode["quantities"]), body)
                check(all(isfinite(item["value"]) for item in loaded["rmse"].values()), body)
                check(removed["rmse"] == {}, body)
                count += 1
                sys.stdout.write(f"{mode['id']} {law} OK\n")
    check(count > 0, "The API advertised no supported combinations")
    sys.stdout.write(f"Verified {count} model, fit-mode and scattering combinations.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    verify(parser.parse_args().base_url)
