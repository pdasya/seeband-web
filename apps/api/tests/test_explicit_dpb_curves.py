"""End-to-end transport of two explicit parabolas on the public HTTP calculation path."""

import runpy
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from running_server import free_port, running_server
from seeband_core import math_module as mm

MODES = {
    "dpb_s": ["seebeck_v_per_k"],
    "dpb_s_rho": ["seebeck_v_per_k", "resistivity_ohm_m"],
    "dpb_s_rho_rh": ["seebeck_v_per_k", "resistivity_ohm_m", "hall_m3_per_c"],
}
TEMPERATURES = [100, 450, 800]
REFERENCE = runpy.run_path(
    str(Path(__file__).resolve().parents[3] / "scripts/verify_p18_contract.py")
)


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    port = free_port()
    with running_server(
        [sys.executable, "-m", "seeband_api"],
        port,
        tmp_path_factory.mktemp("p18-curves") / "api.log",
        {"SEEBAND_API_PORT": str(port)},
    ) as client:
        yield client


def calculated(
    api, config, mode, law, offset, ef, masses, valleys, amplitude, relative, mixed=(0.5, 2.0)
):
    p = dict(m1=masses[0], mass_ratio=masses[1] / masses[0], band_offset_k=offset, fermi_energy=ef)
    if mode != "dpb_s":
        p.update(A=amplitude, F=amplitude, B=relative, G=relative)
        if law == "acPhDis":
            p.update(C=mixed[0], D=mixed[1])
    elif law == "ionized" and relative is not None:
        p["B"] = relative
    response = api.post(
        "/api/calc",
        json=dict(
            model="dpb",
            parameterization="explicit_fermi_v1",
            band_configuration=config,
            fit_mode=mode,
            scattering=law,
            parameters=p,
            band_1_degeneracy=valleys[0],
            band_2_degeneracy=valleys[1],
            min_temperature_k=TEMPERATURES[0],
            max_temperature_k=TEMPERATURES[-1],
            points=3,
        ),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["temperature_k"] == TEMPERATURES
    assert set(body["curves"]) == set(MODES[mode])
    values = np.array([body["curves"][key] for key in MODES[mode]], dtype=float)
    assert np.isfinite(values).all()
    return values


def reference(config, law, offset, ef, masses, valleys, amplitude, relative, temperature):
    # Use the same units/constants as the API. The oracle independently integrates the DOS
    # and transport moments with adaptive quadrature and solves neutrality from E_F at 0 K.
    bands = tuple(
        REFERENCE["Band"](1 if kind == "cb" else -1, edge, mass, count, 1.0)
        for kind, edge, mass, count in zip(
            config.split("_"), (0, offset), masses, valleys, strict=True
        )
    )
    mu, _ = REFERENCE["solve"](bands, REFERENCE["density_zero"](bands, ef), temperature)
    mechanism = {"dis": "alloy/dis", "acPhDis": "acPh"}.get(law, law)
    r, t = REFERENCE["LAWS"][mechanism]
    # Convert the empirical conductivity amplitude in the API to the oracle's time scale.
    factor = {"acPh": 1, "acPhDis": 1, "dis": temperature, "ionized": (temperature / 300) ** 3}[law]
    normalized = []
    for band, weight in zip(
        bands, (1, valleys[1] / valleys[0] * relative * masses[0] / masses[1]), strict=True
    ):
        per_second = (
            mm.e**2
            * 2
            * band.dos_si
            * (mm.kB * temperature) ** 1.5
            / (3 * band.mass_me * mm.me)
            * (1.5 + r)
            * (temperature / 300) ** t
        )
        normalized.append(replace(band, tau0_s=amplitude * factor * weight / per_second))
    if law == "acPhDis":
        # Matthiessen per valley. Ratio of disorder to acoustic rate at 300 K.
        normalized = [
            replace(b, tau0_s=b.tau0_s / (1 + c * 300 / temperature))
            for b, c in zip(normalized, (0.5, 2.0), strict=True)
        ]
    return REFERENCE["transport"](normalized, mu, temperature, mechanism)[:3]


@pytest.mark.parametrize("law", ["acPh", "dis", "acPhDis", "ionized"])
@pytest.mark.parametrize("mode", MODES)
def test_measured_curves_match_moments_and_electron_hole_reflection(api, monkeypatch, mode, law):
    constants = REFERENCE["transport"].__globals__
    for name, value in {"KB": mm.kB, "E": mm.e, "hbar": mm.hbar, "m_e": mm.me}.items():
        monkeypatch.setitem(constants, name, value)
    masses, valleys = (1.7, 0.8), (2, 6)
    amplitude, relative = (1, 1) if mode == "dpb_s" else (40000, 0.8)
    if law == "ionized":
        relative = 4.0
    results = {}
    for config, offset, ef in (("vb_vb", 450, -220), ("cb_cb", -450, 220), ("vb_cb", 450, 150)):
        actual = calculated(
            api, config, mode, law, offset, ef, masses, valleys, amplitude, relative
        )
        expected = np.array(
            [
                reference(
                    config,
                    "acPh" if mode == "dpb_s" and law == "acPhDis" else law,
                    offset,
                    ef,
                    masses,
                    valleys,
                    amplitude,
                    relative,
                    temp,
                )
                for temp in TEMPERATURES
            ]
        ).T
        for key, curve, prediction in zip(
            MODES[mode], actual, expected[: len(actual)], strict=True
        ):
            np.testing.assert_allclose(
                curve, prediction, rtol=1e-6, atol=0, err_msg=f"{config}/{law}/{key}"
            )
        results[config] = actual
    signs = np.array([-1, 1, -1])[: len(MODES[mode]), None]
    assert np.all(results["vb_vb"] > 0)
    np.testing.assert_allclose(results["cb_cb"], signs * results["vb_vb"], rtol=1e-10, atol=0)
    # Reflecting a mixed pair gives CB+VB. Exchange the labels and reset the first edge to zero.
    swapped_amplitude = amplitude * valleys[1] / valleys[0] * relative * masses[0] / masses[1]
    reflected = calculated(
        api,
        "vb_cb",
        mode,
        law,
        450,
        450 - 150,
        masses[::-1],
        valleys[::-1],
        swapped_amplitude,
        1 / relative,
        mixed=(2.0, 0.5),
    )
    np.testing.assert_allclose(reflected, signs * results["vb_cb"], rtol=1e-10, atol=0)


def test_mixed_gap_plateau_and_overlap_with_either_carrier_sign(api, monkeypatch):
    constants = REFERENCE["transport"].__globals__
    for name, value in {"KB": mm.kB, "E": mm.e, "hbar": mm.hbar, "m_e": mm.me}.items():
        monkeypatch.setitem(constants, name, value)
    masses, valleys = (1.7, 0.8), (2, 6)
    mode, law = "dpb_s_rho_rh", "acPh"
    args = masses, valleys, 40000, 0.8
    left = calculated(api, "vb_cb", mode, law, 450, 0, *args)
    right = calculated(api, "vb_cb", mode, law, 450, 450, *args)
    np.testing.assert_array_equal(left, right)
    for ef, sign in ((-420, -1), (-30, 1)):
        bands = [
            REFERENCE["Band"](s, edge, mass, n, 1)
            for s, edge, mass, n in zip((-1, 1), (0, -450), masses, valleys, strict=True)
        ]
        assert np.sign(REFERENCE["density_zero"](bands, ef)) == sign
        actual = calculated(api, "vb_cb", mode, law, -450, ef, *args)
        expected = np.array([reference("vb_cb", law, -450, ef, *args, t) for t in TEMPERATURES]).T
        np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=0)


@pytest.mark.parametrize(
    "config,offset,ef", [("vb_vb", 450, -220), ("cb_cb", -450, 220), ("vb_cb", 450, 150)]
)
def test_ionized_s_only_default_and_held_weight_across_fit_modes(api, config, offset, ef):
    # Unequal edges give unequal partial Seebeck coefficients and a visible B effect.
    def curve(mode, weight):
        return calculated(api, config, mode, "ionized", offset, ef, (1, 2), (1, 3), 40000, weight)

    default = curve("dpb_s", None)
    np.testing.assert_array_equal(default, curve("dpb_s", 1))
    chosen = curve("dpb_s", 4)
    assert np.max(np.abs(default - chosen)) > 1e-6
    for mode in ("dpb_s_rho", "dpb_s_rho_rh"):
        np.testing.assert_allclose(chosen[0], curve(mode, 4)[0], rtol=1e-10)


def test_conditional_coulomb_benchmark_from_partial_conductivities(api):
    # Equal edges remove the F2 ratio; the conditional Coulomb prefactor is N*M = 6.
    for weight, expected in ((1, 1.5), (4, 6)):
        response = api.post(
            "/api/calc",
            json=dict(
                model="dpb",
                parameterization="explicit_density_v1",
                band_configuration="cb_cb",
                fit_mode="dpb_s_rho_rh",
                scattering="ionized",
                kind="electrical_conductivity_by_band",
                net_electron_density_per_m3=2e24,
                band_1_degeneracy=1,
                band_2_degeneracy=3,
                parameters=dict(
                    m1=1, mass_ratio=2, band_offset_k=0, A=40000, B=weight, F=40000, G=1
                ),
                min_temperature_k=100,
                max_temperature_k=500,
                points=3,
            ),
        )
        assert response.status_code == 200, response.text
        curves = response.json()["curves"]
        ratio = (
            np.array(curves["electrical_conductivity_band_2_s_per_m"])
            / curves["electrical_conductivity_band_1_s_per_m"]
        )
        np.testing.assert_allclose(ratio, expected, rtol=1e-10, atol=0)
