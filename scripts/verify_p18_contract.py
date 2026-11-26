"""Independent synthetic design oracle for #166; no new production physics.

Run from the checkout with NumPy/SciPy installed::

    PYTHONPATH=packages/seeband_core/src python scripts/verify_p18_contract.py

Contract: 3D isotropic unbounded parabolas, s=+1 CB / -1 VB, positive
DOS/transport mass in m_e, valley count excluding spin, spin multiplicity 2.
E/k_B and mu/k_B are reported in K; D=sum(s_i population_i)=n-p in m^-3
is fixed at every T>0. This is not the legacy E_F0 parameterization.

Transport is a synthetic weak-field relaxation-time anchor, not a claim about
microscopic amplitudes: tau=tau0*(T/300 K)^t*x^r, x=kinetic energy/(k_B T).
acPh: (r,t)=(-1/2,-1); alloy/dis: (-1/2,0); ionized: (3/2,0), unscreened.
S [V/K], rho [ohm m], R_H [m^3/C], electronic open-circuit kappa [W/(m K)].
DOS quadrature and transport moments here do not call production kernels.
Only the explicitly marked legacy comparison imports production code.
"""

# ruff: noqa: T201 -- this executable oracle reports its evidence to stdout.

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import scipy
from scipy.constants import Boltzmann as KB
from scipy.constants import elementary_charge as E
from scipy.constants import hbar, m_e
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import expit


@dataclass(frozen=True)
class Band:
    s: int
    edge_k: float
    mass_me: float
    valleys: int
    tau0_s: float

    def __post_init__(self):
        assert self.s in (-1, 1)
        assert self.mass_me > 0 and self.valleys > 0 and self.tau0_s > 0

    @property
    def dos_si(self):
        # Spin-2 DOS per volume per energy: C sqrt(epsilon), J^-3/2 m^-3.
        return self.valleys / (2 * np.pi**2) * (2 * self.mass_me * m_e / hbar**2) ** 1.5


def integral(function, eta, tolerance=2e-10):
    """Resolve occupied interval and Fermi window, then integrate to infinity."""
    points = sorted({0.0, max(0.0, eta - 12), max(0.0, eta), max(0.0, eta) + 12})
    return sum(
        quad(function, a, b, epsabs=1e-13, epsrel=tolerance)[0]
        for a, b in zip(points, [*points[1:], np.inf], strict=True)
    )


def population(band, mu_k, temperature_k, tolerance=2e-10):
    eta = band.s * (mu_k - band.edge_k) / temperature_k
    # Remove exp(eta) before integration: absolute quad tolerance must not
    # dominate populations in a wide gap. The remaining integral is O(1).
    if eta <= 0:
        fhalf = np.exp(eta) * integral(
            lambda x: np.sqrt(x) * np.exp(-x) * expit(x - eta), eta, tolerance
        )
    else:
        fhalf = integral(lambda x: np.sqrt(x) * expit(eta - x), eta, tolerance)
    return band.dos_si * (KB * temperature_k) ** 1.5 * fhalf


def density(bands, mu_k, temperature_k, tolerance=2e-10):
    return sum(b.s * population(b, mu_k, temperature_k, tolerance) for b in bands)


def density_zero(bands, mu_k):
    return sum(
        b.s * b.dos_si * (2 / 3) * (KB * max(0, b.s * (mu_k - b.edge_k))) ** 1.5 for b in bands
    )


def solve(bands, doping_per_m3, temperature_k, tolerance=2e-10):
    assert temperature_k > 0 and np.isfinite(doping_per_m3)
    signs = {b.s for b in bands}
    if len(signs) == 1 and next(iter(signs)) * doping_per_m3 <= 0:
        raise ValueError("same-type D=0 has only an infinite-mu limit; wrong sign has no root")
    # Fixed scale for bracketing; final certification uses populations at the root.
    scale = max(abs(doping_per_m3), sum(population(b, b.edge_k, temperature_k) for b in bands))

    def balance(mu):
        return (density(bands, mu, temperature_k, tolerance) - doping_per_m3) / scale

    width = max(temperature_k, *(abs(b.edge_k) for b in bands), 1.0)
    for _ in range(40):
        if balance(-width) <= 0 <= balance(width):
            break
        width *= 2
    else:
        raise AssertionError("independent root not bracketed")
    mu_k = brentq(balance, -width, width, xtol=1e-11, rtol=4 * np.finfo(float).eps)
    populations = [population(b, mu_k, temperature_k, tolerance) for b in bands]
    residual = abs(sum(b.s * n for b, n in zip(bands, populations, strict=True)) - doping_per_m3)
    residual /= max(sum(populations), abs(doping_per_m3))
    assert residual <= 1e-12
    return mu_k, residual


LAWS = {"acPh": (-0.5, -1), "alloy/dis": (-0.5, 0), "ionized": (1.5, 0)}


def transport(bands, mu_k, temperature_k, law, *, conductivity_only=False):
    r, t = LAWS[law]
    sigma = alpha = heat = hall = 0.0
    for b in bands:
        eta = b.s * (mu_k - b.edge_k) / temperature_k

        def window(x, eta=eta):
            if eta <= 0:
                return np.exp(-x) * expit(x - eta) ** 2
            return expit(x - eta) * expit(eta - x)

        prefactor = b.dos_si * (KB * temperature_k) ** 1.5 * 2 / (3 * b.mass_me * m_e)
        prefactor *= np.exp(min(eta, 0.0))
        tau = b.tau0_s * (temperature_k / 300) ** t
        moments = [
            integral(
                lambda x, window=window, eta=eta, j=j: x ** (1.5 + r) * window(x) * (x - eta) ** j,
                eta,
            )
            * prefactor
            * tau
            * (KB * temperature_k) ** j
            for j in range(3)
        ]
        q = -b.s * E
        sigma += q**2 * moments[0]
        alpha += q * moments[1] / temperature_k
        heat += moments[2] / temperature_k
        hall += (
            q**3
            * prefactor
            * tau**2
            / (b.mass_me * m_e)
            * integral(lambda x, window=window: x ** (1.5 + 2 * r) * window(x), eta)
        )
    if conductivity_only:
        return sigma
    values = np.array(
        [alpha / sigma, 1 / sigma, hall / sigma**2, heat - temperature_k * alpha**2 / sigma]
    )
    assert np.isfinite(values).all() and values[1] > 0 and values[3] > 0
    return values


def verify_synthetic():
    vb = Band(-1, 0.0, 1.7, 2, 1e-14)
    other = Band(-1, -450.0, 0.8, 3, 1.7e-14)
    configurations = {"VB+VB": (vb, other), "VB+CB": (vb, replace(other, s=1, edge_k=650.0))}
    configurations["CB+CB"] = tuple(
        replace(b, s=-b.s, edge_k=-b.edge_k) for b in configurations["VB+VB"]
    )
    temperatures_k = (100.0, 300.0, 800.0)
    maximum_residual = maximum_refinement_k = 0.0
    etas = []
    roots = transports = rejected = 0
    for name, bands in configurations.items():
        dopings = (
            (-2e24, 0.0, 2e24) if name == "VB+CB" else ((-2e24,) if name == "VB+VB" else (2e24,))
        )
        for doping in dopings:
            mus = []
            for temperature in temperatures_k:
                mu, residual = solve(bands, doping, temperature)
                etas.extend(b.s * (mu - b.edge_k) / temperature for b in bands)
                refined, _ = solve(bands, doping, temperature, 2e-12)
                maximum_refinement_k = max(maximum_refinement_k, abs(refined - mu))
                maximum_residual = max(maximum_residual, residual)
                mirror = tuple(replace(b, s=-b.s, edge_k=-b.edge_k) for b in bands)
                mirrored, _ = solve(mirror, -doping, temperature)
                relabeled, _ = solve(bands[::-1], doping, temperature)
                shifted = tuple(replace(b, edge_k=b.edge_k + 117.0) for b in bands)
                shifted_mu, _ = solve(shifted, doping, temperature)
                np.testing.assert_allclose(shifted_mu, mu + 117.0, atol=2e-8, rtol=1e-11)
                # g -> 2g, m -> 1.3m changes absolute density by 2*1.3^1.5.
                scaled = tuple(
                    replace(b, mass_me=1.3 * b.mass_me, valleys=2 * b.valleys) for b in bands
                )
                scaled_mu, _ = solve(scaled, doping * 2 * 1.3**1.5, temperature)
                np.testing.assert_allclose(
                    [mirrored, relabeled, scaled_mu], [-mu, mu, mu], atol=2e-8, rtol=1e-11
                )
                assert density(bands, mu + 1.0, temperature) > density(bands, mu - 1.0, temperature)
                for law in LAWS:
                    actual = transport(bands, mu, temperature, law)
                    np.testing.assert_allclose(
                        transport(shifted, shifted_mu, temperature, law),
                        actual,
                        rtol=2e-9,
                        atol=1e-18,
                    )
                    np.testing.assert_allclose(
                        transport(mirror, mirrored, temperature, law),
                        actual * [-1, 1, -1, 1],
                        rtol=2e-9,
                        atol=1e-18,
                    )
                    np.testing.assert_allclose(
                        transport(bands[::-1], relabeled, temperature, law),
                        actual,
                        rtol=2e-9,
                        atol=1e-18,
                    )
                    sigma_scale = 2 * 1.3**0.5
                    np.testing.assert_allclose(
                        transport(scaled, scaled_mu, temperature, law),
                        actual * [1, 1 / sigma_scale, 1 / (2 * 1.3**1.5), sigma_scale],
                        rtol=2e-9,
                        atol=1e-18,
                    )
                    if name != "VB+CB":
                        # Holes have positive S/R_H, electrons negative, q=-s*e.
                        assert bands[0].s * actual[0] < 0 and bands[0].s * actual[2] < 0
                    transports += 1
                mus.append(round(mu, 6))
                roots += 1
            print(f"{name}: D={doping:+.3e} m^-3; mu/k_B={mus} K at T={temperatures_k} K")
        if name != "VB+CB":
            for doping in (0.0, 2e24 if name == "VB+VB" else -2e24):
                for temperature in temperatures_k:
                    try:
                        solve(bands, doping, temperature)
                    except ValueError:
                        rejected += 1
                    else:
                        raise AssertionError("inadmissible same-type density accepted")
    # Independent normalization anchor: Maxwell-Boltzmann limit, including spin 2.
    eta = -20.0
    mb = 2 * vb.valleys * (vb.mass_me * m_e * KB * 300 / (2 * np.pi * hbar**2)) ** 1.5 * np.exp(eta)
    np.testing.assert_allclose(population(vb, -eta * 300, 300), mb, rtol=2e-9)
    # Coincident identical channels reduce exactly to a single band with twice g.
    for temperature in temperatures_k:
        double_mu, _ = solve((vb, vb), -2e24, temperature)
        single = replace(vb, valleys=2 * vb.valleys)
        single_mu, _ = solve((single,), -2e24, temperature)
        np.testing.assert_allclose(single_mu, double_mu, atol=1e-9)
        for law in LAWS:
            np.testing.assert_allclose(
                transport((single,), single_mu, temperature, law),
                transport((vb, vb), double_mu, temperature, law),
                rtol=2e-10,
            )
        # A finite distant edge suppresses population/conductivity; no zero mass/tau.
        for sign in (-1, 1):
            first = replace(vb, s=sign)
            remote = replace(other, s=sign, edge_k=sign * 60000.0)
            single_mu, _ = solve((first,), sign * 2e24, temperature)
            two_mu, _ = solve((first, remote), sign * 2e24, temperature)
            np.testing.assert_allclose(two_mu, single_mu, atol=1e-8, rtol=1e-11)
            assert population(remote, two_mu, temperature) / abs(2e24) < 1e-20
            for law in LAWS:
                standalone = transport((first,), single_mu, temperature, law)
                suppressed = transport((first, remote), two_mu, temperature, law)
                np.testing.assert_allclose(suppressed, standalone, rtol=2e-9, atol=1e-18)
                # rho=1/sigma, so this independently bounds the remote conductivity.
                remote_sigma = transport(
                    (remote,), two_mu, temperature, law, conductivity_only=True
                )
                assert standalone[1] * remote_sigma < 1e-18
    assert maximum_refinement_k < 2e-7
    print(
        f"synthetic PASS: {roots} roots, {rejected} domain rejections, "
        f"{transports} finite transport cases; mirror/relabel/scaling/shift/SPB limits PASS"
    )
    print(
        f"main-case max root-population normalized density residual={maximum_residual:.3e}; "
        f"tighter quadrature delta_mu={maximum_refinement_k:.3e} K"
    )
    print(
        f"main-fixture eta_i span [{min(etas):.3f}, {max(etas):.3f}]; "
        "MB spin/valley normalization PASS"
    )
    print(
        "SPB suppression PASS: finite remote edges +/-60000 K; population <1e-20, "
        "conductivity <1e-18 of first; mu/S/rho/Hall/kappa recover standalone"
    )


def verify_wide_offsets():
    """Independent momentum quadrature and asymptotic anchors at +/-3 eV."""

    def momentum_population(band, mu, temperature):
        eta = band.s * (mu - band.edge_k) / temperature

        # x=u^2 removes the DOS square-root endpoint; scale Boltzmann tails.
        def integrand(u):
            occupation = np.exp(-u * u) * expit(u * u - eta) if eta <= 0 else expit(eta - u * u)
            return 2 * u * u * occupation

        center = np.sqrt(max(0.0, eta))
        points = sorted({0.0, max(0.0, center - 3), center, center + 3})
        value = sum(
            quad(integrand, a, b, epsabs=1e-14, epsrel=2e-12)[0]
            for a, b in zip(points, [*points[1:], np.inf], strict=True)
        )
        return band.dos_si * (KB * temperature) ** 1.5 * np.exp(min(eta, 0.0)) * value

    vb = Band(-1, 0.0, 1.7, 2, 1e-14)
    max_delta_k = max_residual = max_mb_k = 0.0
    for offset_ev in (3.0, -3.0):
        cb = Band(1, offset_ev * E / KB, 0.8, 6, 1.7e-14)
        bands = (vb, cb)
        # Nonzero D is fixed from a T=0 anchor, 1200 K inside the CB for a
        # true gap, and 300 K above the VB edge for a strongly degenerate overlap.
        doping = density_zero(bands, cb.edge_k + 1200 if offset_ev > 0 else 300)
        for doping_value in (0.0, doping):
            for temperature in (300.0, 800.0):
                mu, residual = solve(bands, doping_value, temperature)
                scale = max(
                    abs(doping_value), sum(momentum_population(b, mu, temperature) for b in bands)
                )

                def independent_balance(
                    value,
                    bands=bands,
                    temperature=temperature,
                    doping_value=doping_value,
                    scale=scale,
                ):
                    return (
                        sum(b.s * momentum_population(b, value, temperature) for b in bands)
                        - doping_value
                    ) / scale

                reference = brentq(
                    independent_balance, mu - 1, mu + 1, xtol=1e-11, rtol=4 * np.finfo(float).eps
                )
                delta = abs(reference - mu)
                assert delta < 2e-7
                assert abs(independent_balance(mu)) < 2e-11
                max_delta_k, max_residual = max(max_delta_k, delta), max(max_residual, residual)
                if offset_ev > 0 and doping_value == 0:
                    mb_mu = cb.edge_k / 2 + temperature / 2 * np.log(vb.dos_si / cb.dos_si)
                    max_mb_k = max(max_mb_k, abs(mu - mb_mu))
                    assert abs(mu - mb_mu) < 2e-6
                for law in LAWS:
                    transport(bands, mu, temperature, law)
                etas = [b.s * (mu - b.edge_k) / temperature for b in bands]
                print(
                    f"wide offset={offset_ev:+g} eV, D={doping_value:+.6e} m^-3, "
                    f"T={temperature:g} K: mu/k_B={mu:.9f} K, "
                    f"eta={etas[0]:.3f}/{etas[1]:.3f}, residual={residual:.3e}"
                )
        # Endpoint-root regression: selected D makes mu=-initial_width exact.
        endpoint = -max(300.0, abs(cb.edge_k))
        endpoint_doping = density(bands, endpoint, 300.0)
        endpoint_mu, _ = solve(bands, endpoint_doping, 300.0)
        assert endpoint_mu == endpoint
        if offset_ev < 0:
            # Degenerate overlap intrinsic root approaches its analytic T=0 value.
            a, b = vb.dos_si ** (2 / 3), cb.dos_si ** (2 / 3)
            zero_mu = b * cb.edge_k / (a + b)
            low_mu, _ = solve(bands, 0.0, 1.0)
            assert abs(low_mu - zero_mu) < 1e-3
    print(
        f"wide-offset PASS: 8 roots/24 transport cases, exact endpoint roots; "
        f"max residual={max_residual:.3e}, momentum-quadrature delta_mu={max_delta_k:.3e} K, "
        f"intrinsic-gap MB delta_mu={max_mb_k:.3e} K; overlap T=1 K limit PASS"
    )


def verify_legacy():
    # Compatibility evidence only: current source core is never used for expected values.
    from seeband_core import math_module as mm
    from seeband_core.band_models import DpbModel
    from seeband_core.model_interface import CurveRequest

    source_root = Path(__file__).resolve().parents[1] / "packages/seeband_core/src"
    assert Path(mm.__file__).resolve().is_relative_to(source_root), (
        "use this checkout's source PYTHONPATH"
    )
    temperatures = np.linspace(100.0, 800.0, 3)
    max_delta_k = max_density_relative = 0.0
    for sign in (-1, 1):
        bands = (
            Band(-1, 0.0, 1.7, 2, 1e-14),
            Band(sign, 650.0 if sign > 0 else -450.0, 0.8, 6, 1.7e-14),
        )
        gap, ratio = bands[1].edge_k, bands[1].valleys / bands[0].valleys
        public_mass_ratio = sign * bands[1].mass_me / bands[0].mass_me
        for ef0 in (-300.0, 1000.0) if sign > 0 else (-300.0,):
            doping = density_zero(bands, ef0)
            expected = np.array([solve(bands, doping, t)[0] for t in temperatures])
            legacy = mm.dpb_chemPot_vs_temp(
                temperatures, gap, public_mass_ratio / ratio, ef0, ratio
            )
            delta = float(np.max(abs(legacy - expected)))
            # Legacy F_1/2 interpolation/asymptotics and pre-2019 k_B differ.
            assert delta < 1e-3, f"legacy delta {delta} K exceeds compatibility budget"
            request = CurveRequest(
                "dpb_s_rho_rh",
                dict(
                    m_eff=public_mass_ratio,
                    band_gap=gap,
                    fermi_energy=ef0,
                    m1=bands[0].mass_me,
                    A=1e5,
                    B=1.0,
                    C=1.0,
                    D=1.0,
                    F=1e5,
                    G=1.0,
                ),
                float(temperatures[0]),
                float(temperatures[-1]),
                len(temperatures),
                scattering="acPh",
                kind="carrier_concentration_by_band",
                band_1_degeneracy=bands[0].valleys,
                band_2_degeneracy=bands[1].valleys,
            )
            result = DpbModel().calculate(request)
            differences = []
            for index, band in enumerate(bands, 1):
                actual = (
                    np.asarray(result.curves[f"carrier_concentration_band_{index}_per_cm3"]) * 1e6
                )
                independent = np.array(
                    [
                        band.s * population(band, mu, t)
                        for mu, t in zip(expected, temperatures, strict=True)
                    ]
                )
                differences.append(float(np.max(abs(actual - independent) / abs(independent))))
            relative = max(differences)
            assert relative < 2e-6, f"legacy physical population mismatch {relative}"
            max_delta_k, max_density_relative = (
                max(max_delta_k, delta),
                max(max_density_relative, relative),
            )
            print(
                f"legacy VB+{'CB' if sign > 0 else 'VB'}: E_F0/k_B={ef0:g} K "
                f"-> D={doping:+.6e} m^-3; max delta_mu={delta:.3e} K; "
                f"core-model population relative delta={relative:.3e}"
            )
    print(
        "legacy PASS: source core/model entry point, m1=1.7 m_e, m2=0.8 m_e, "
        f"(N1,N2)=(2,6); maxima {max_delta_k:.3e} K / {max_density_relative:.3e}"
    )


if __name__ == "__main__":
    print(f"P18 SYNTHETIC DESIGN ORACLE; NumPy {np.__version__}, SciPy {scipy.__version__}")
    verify_synthetic()
    verify_wide_offsets()
    verify_legacy()
    print(
        "Limits: selected finite positive T fixtures, including +/-3 eV at 300/800 K; "
        "isotropic spin-2 parabolas; "
        "no anisotropy, screening, fit/identifiability or new production support asserted."
    )
    print(
        "Transport amplitudes are synthetic; compatibility budgets: 1e-3 K mu, "
        "2e-6 relative population (legacy FD approximation/constants). "
        "Human physics approval remains separate."
    )
