"""Check the three-band S-only flat-profile example in design §6.2, in SI.

The input E_F fixes the zero-temperature carrier excess. For the separated
VB/CB edges below every E_F within the gap gives zero excess and the same
finite-temperature root. A noiseless least-squares objective bounded below
by zero has a known profile minimum wherever this witness attains zero.
"""

# ruff: noqa: T201 -- review evidence is emitted on stdout.
import numpy as np
from verify_mixed_scattering_design import KB, Band, E
from verify_parabolic_mass_identifiability import TEMPERATURES_K, curves


def main():
    ev_to_k = E / KB
    bands = (
        Band(-1, 0.0, 1.0, 1, 0),
        Band(1, 0.02 * ev_to_k, 1.4, 1, 0),
        Band(-1, -0.12 * ev_to_k, 0.8, 1, 0),
    )

    def seebeck(ef_ev):
        return curves(bands, (1, 1, 1), ef_ev * ev_to_k)[:, 2]

    reference = seebeck(0.01)
    if not np.isfinite(reference).all() or np.ptp(reference) < 1e-6:
        raise ValueError("Expected a finite, temperature-dependent Seebeck curve")
    profile = np.array([seebeck(ef_ev) for ef_ev in (0, 0.005, 0.01, 0.015, 0.02)])
    delta = np.max(np.abs(profile - reference))
    # Scaled sum of squared residuals, with S expressed numerically in µV/K.
    loss = np.max(np.sum(((profile - reference) * 1e6) ** 2, axis=1))
    outside = np.array([np.max(np.abs(seebeck(ef_ev) - reference)) for ef_ev in (-0.01, 0.03)])
    if not (delta <= 1e-12 and np.all(np.isfinite(outside) & (outside > 1e-6))):
        raise ValueError(f"Flat interval or outside-gap controls failed: {delta=}, {outside=}")
    print("Synthetic three-band S-only, acPh, VB/CB/VB, edges 0, 0.02, -0.12 eV.")
    print("Single-valley masses [1, 1.4, 0.8] m_e. All valley counts and b weights are 1.")
    print(
        f"T [K] = {list(TEMPERATURES_K)}; S [uV/K] = "
        + ", ".join(f"{v * 1e6:.5f}" for v in reference)
    )
    print(f"Five E_F points from 0 to 0.02 eV: max |delta S|={delta:.3e} V/K; max loss={loss:.3e}.")
    print(
        "Controls at -0.01 and 0.03 eV: max |delta S| [uV/K] = "
        + ", ".join(f"{v * 1e6:.5f}" for v in outside)
    )
    print("PASS: the interval endpoints are band edges. Statistical uncertainty was not estimated.")


if __name__ == "__main__":
    main()
