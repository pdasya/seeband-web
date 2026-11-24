"""Run the design evidence's numerical assertions through its real entrypoints."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = "docs/superpowers/specs/band-composition-v0.7/evidence"


@pytest.mark.parametrize(
    "entrypoint,args,checkpoint",
    [
        pytest.param(
            "scripts/verify_band_composition_design.py",
            (),
            "PASS: gap E_F equivalence, all permutations",
            id="composition",
        ),
        pytest.param(
            "scripts/verify_spb_design_coefficients.py",
            (),
            "PASS 36 independent comparisons",
            id="spb",
        ),
        pytest.param("scripts/verify_skb_design_reference.py", (), "Table 2 CB:", id="skb"),
        pytest.param(
            "scripts/verify_skb_design_reference.py",
            ("--core",),
            "PASS epsilon=1e-4,1e-6,1e-8 approach monotonic",
            id="skb-core",
        ),
        pytest.param(
            "scripts/verify_mixed_scattering_design.py", (), "Matthiessen vs formula", id="mixed"
        ),
        pytest.param(
            "scripts/verify_mixed_scattering_design.py",
            ("--legacy",),
            "Legacy math_module comparison PASS",
            id="mixed-legacy",
        ),
        pytest.param(
            "scripts/verify_parabolic_mass_identifiability.py",
            (),
            "PASS selected synthetic references only",
            id="mass",
        ),
        pytest.param(
            "scripts/verify_three_band_s_profile.py",
            (),
            "PASS: the interval endpoints are band edges",
            id="three-band-profile",
        ),
        pytest.param(
            f"{EVIDENCE}/verify_valley_counts.py",
            (),
            "42 invalid valley inputs rejected",
            id="valley-counts",
        ),
        pytest.param(
            f"{EVIDENCE}/verify_kane_weights.py",
            (),
            "dimensional and relative S agree",
            id="kane-weights",
        ),
    ],
)
def test_band_design_evidence(entrypoint: str, args: tuple[str, ...], checkpoint: str) -> None:
    # SKB --core changes imported SPB constants: isolate every entrypoint so its
    # checks cannot depend on another test's imports or global mutations.
    env = os.environ.copy()
    env.pop("PYTHONOPTIMIZE", None)
    env["PYTHONPATH"] = os.pathsep.join(
        (str(ROOT / "scripts"), str(ROOT / "packages/seeband_core/src"))
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / entrypoint), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert checkpoint in result.stdout, result.stdout + result.stderr
