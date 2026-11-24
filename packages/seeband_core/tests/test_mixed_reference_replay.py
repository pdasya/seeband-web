"""Exercise the MIX compatibility contract through its executable CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "docs/superpowers/specs/band-composition-v0.7/evidence/mixed_reference.json"


def replay(path):
    env = os.environ.copy()
    env.pop("PYTHONOPTIMIZE", None)
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_mixed_scattering_design.py"),
            "--reference",
            str(path),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_mixed_replay_identifies_out_of_tolerance_quantity(tmp_path):
    data = json.loads(REFERENCE.read_text())
    data["cases"][0]["outputs"]["rho"] *= 1.01
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    result = replay(path)
    assert result.returncode != 0
    assert "MIX replay FAIL" in result.stderr
    assert "rho" in result.stderr and "temperature_k" in result.stderr


@pytest.mark.parametrize("quantity", ["rho", "S", "RH", "L"])
def test_mixed_replay_rejects_relative_drift(tmp_path, quantity):
    data = json.loads(REFERENCE.read_text())
    data["cases"][0]["outputs"][quantity] *= 1 + 1e-6
    path = tmp_path / "drift.json"
    path.write_text(json.dumps(data))
    result = replay(path)
    assert result.returncode != 0
    assert f"MIX replay FAIL: {quantity} [" in result.stderr
    assert "inputs=" in result.stderr and "budget=" in result.stderr


@pytest.mark.parametrize("quantity,delta", [("S", 1e-11), ("RH", 1e-16)])
def test_mixed_replay_rejects_cancellation_drift(tmp_path, quantity, delta):
    data = json.loads(REFERENCE.read_text())
    case = next(c for c in data["cases"] if c["id"].startswith("compensated/"))
    assert abs(case["outputs"][quantity]) < delta / 1000
    case["outputs"][quantity] += delta
    path = tmp_path / "cancelled.json"
    path.write_text(json.dumps(data))
    result = replay(path)
    assert result.returncode != 0
    assert f"MIX replay FAIL: {quantity} [" in result.stderr
    assert "compensated/" in result.stderr and "temperature_k" in result.stderr


@pytest.mark.parametrize(
    "damage",
    [
        "missing-case",
        "extra-case",
        "duplicate-case",
        "missing-output",
        "input",
        "units",
        "nan",
        "inf",
    ],
)
def test_mixed_replay_rejects_incomplete_or_nonfinite_reference(tmp_path, damage):
    data = json.loads(REFERENCE.read_text())
    if damage == "missing-case":
        data["cases"].pop()
    elif damage == "extra-case":
        data["cases"].append({**data["cases"][0], "id": "unexpected"})
    elif damage == "duplicate-case":
        data["cases"].append(data["cases"][0])
    elif damage == "missing-output":
        del data["cases"][0]["outputs"]["L"]
    elif damage == "input":
        data["cases"][0]["inputs"]["temperature_k"] += 1
    elif damage == "units":
        data["units"]["S"] = "microV/K"
    else:
        data["cases"][0]["outputs"]["S"] = float(damage)
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(data))
    result = replay(path)
    assert result.returncode != 0
    assert "MIX replay FAIL:" in result.stderr


def test_mixed_replay_accepts_small_rounding_noise_including_cancellation(tmp_path):
    data = json.loads(REFERENCE.read_text())
    for case in data["cases"]:
        for quantity, value in case["outputs"].items():
            budget = data["tolerances"][quantity]
            case["outputs"][quantity] += (budget["atol"] + budget["rtol"] * abs(value)) * 1e-3
    path = tmp_path / "noise.json"
    path.write_text(json.dumps(data))
    result = replay(path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MIX reference replay PASS 73 cases" in result.stdout
