#!/usr/bin/env python3
"""Replay P18 evidence without preparing or modifying a caller-owned checkout.

From the review root:
    uv run --frozen python docs/superpowers/specs/band-composition-v0.7/evidence/replay_p18.py
Add --only <row ID> to run one row (regression ID: DPB-HALL-REGRESSION).
Requires Git and, when the pinned objects are absent locally, public GitHub access.
Uses this review's frozen Python environment and reference scripts with the pinned
P18 core. Fresh temporary clones are removed on exit; historical evidence is untouched.
"""

# ruff: noqa: T201 -- standalone evidence command.
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PUBLIC_REPOSITORY = "https://github.com/pdasya/seeband-web.git"
PUBLIC_BRANCH = "refs/heads/codex/p18-hall-quadrature"
ROWS = ("P18-BASE", "DPB-HALL", "DPB-HALL-FIX", "MIX-P18", "DPB-HALL-REGRESSION")


def validate_old_hall(returncode, output, expected):
    """A failed import or unrelated assertion must never count as the old Hall result."""
    match = re.search(
        r"CB\+CB dis 800 K: R_H \[m\^3/C\], oracle \[m\^3/C\], scaled error "
        r"([-+\deE.]+) ([-+\deE.]+) ([-+\deE.]+)",
        output,
    )
    if returncode != 1 or not match:
        raise RuntimeError("DPB-HALL did not reproduce the documented numerical failure")
    actual, oracle, error = map(float, match.groups())
    if not (
        math.isclose(actual, -7.038047601642028e-6, rel_tol=1e-9)
        and math.isclose(oracle, -7.038039355547361e-6, rel_tol=1e-9)
        and math.isclose(error, expected, rel_tol=1e-6)
        and output.rstrip().endswith(
            f"AssertionError: DPB-HALL design budget exceeded: {error:.12g} >= 1e-6"
        )
    ):
        raise RuntimeError("DPB-HALL failed outside the documented CB+CB/dis/800 K budget")


def command(args, cwd, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Command failed: {args!r}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=ROWS, help="Replay only this row; default: all five")
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent
    review = evidence.parents[4]
    manifest = json.loads((evidence.parent / "evidence.json").read_text())
    before, after = (manifest[key] for key in ("archived_p18_revision", "corrected_p18_revision"))
    for revision in (before, after):
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise RuntimeError(f"Expected a pinned full commit: {revision!r}")
    selected = [args.only] if args.only else ROWS
    with tempfile.TemporaryDirectory(prefix="seeband-p18-replay-") as temporary:
        checkout = Path(temporary) / "p18"
        command(["git", "clone", "--shared", "--no-checkout", str(review), str(checkout)], review)
        revisions = {before if row in ROWS[:2] or row == "MIX-P18" else after for row in selected}
        for revision in sorted(revisions):
            present = subprocess.run(
                ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
                cwd=checkout,
                capture_output=True,
            )
            if present.returncode:
                command(["git", "fetch", "--no-tags", PUBLIC_REPOSITORY, PUBLIC_BRANCH], checkout)
                break
        for row in selected:
            revision = before if row in ROWS[:2] or row == "MIX-P18" else after
            command(["git", "checkout", "--detach", revision], checkout)
            if command(["git", "rev-parse", "HEAD"], checkout) != revision:
                raise RuntimeError("Replay checkout revision mismatch")
            env = os.environ.copy()
            core = checkout / "packages/seeband_core/src"
            # Avoid caller PYTHONPATH, pytest options/plugins, and source bytecode writes.
            env.update(
                PYTHONPATH=os.pathsep.join((str(core), str(review / "scripts"))),
                PYTHONDONTWRITEBYTECODE="1",
                PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            )
            for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONHOME", "PYTHONOPTIMIZE"):
                env.pop(key, None)
            command(
                [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; import seeband_core; "
                    "assert Path(seeband_core.__file__).resolve().is_relative_to(Path.cwd()), "
                    "seeband_core.__file__",
                ],
                checkout,
                env,
            )
            if row == "P18-BASE":
                payload = [
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "packages/seeband_core/tests/test_carrier_domain.py",
                    "packages/seeband_core/tests/test_explicit_transport.py",
                    "packages/seeband_core/tests/test_explicit_dpb_fit.py",
                ]
                required = ("113 passed",)
            elif row == "DPB-HALL-REGRESSION":
                payload = [
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "packages/seeband_core/tests/test_transport_hall_quadrature.py",
                ]
                required = ("28 passed",)
            elif row == "MIX-P18":
                payload = [str(review / "scripts/verify_mixed_scattering_design.py"), "--legacy"]
                required = (
                    "PASS 72 temperature/configuration/mode cases",
                    "Legacy math_module comparison PASS [rho,S,RH]",
                )
            else:
                payload = [str(evidence / "verify_explicit_curves_spb.py")]
                required = (
                    "PASS: 27 mode/configuration/scattering combinations; 81 temperature vectors",
                    "DPB-HALL passed: 27 Hall points; scaled error < 1e-7; design budget 1e-6.",
                )
            print(f"RUN {row} revision={revision} options={' '.join(payload)}", flush=True)
            result = subprocess.run(
                [sys.executable, *payload], cwd=checkout, env=env, capture_output=True, text=True
            )
            output = result.stdout + result.stderr
            if row == "DPB-HALL":
                expected = next(check for check in manifest["checks"] if check["id"] == row)
                validate_old_hall(
                    result.returncode, output, expected["metrics"]["scaled_error_Hall"]
                )
                print(
                    "PASS DPB-HALL: expected CB+CB/dis/800 K Hall budget failure "
                    f"(exit 1; scaled error={expected['metrics']['scaled_error_Hall']:.12g})"
                )
            else:
                if result.returncode or not all(marker in output for marker in required):
                    raise RuntimeError(f"{row} did not pass its replay contract:\n{output}")
                for line in output.splitlines():
                    if any(marker in line for marker in required) or line.startswith("MAX ERRORS"):
                        print(line)
                print(f"PASS {row} (exit 0)")
    print("Replay complete; historical evidence files unchanged.")


if __name__ == "__main__":
    main()
