# DPB Hall prefactor (P2, #81)

The DPB Hall coefficient now recovers the single-band limit in all three scattering
modes. Removing the extra factor 2 from each denominator doubles R_H at fixed
parameters. The scattering exponents, chemical-potential solver and band conventions
are unchanged. Negative band-2 weights remain a separate known issue (#104).

## Independent reference

Use unnormalised Fermi integrals F_j(η) = ∫₀∞ xʲ/(1+exp(x−η)) dx. For the
implemented scattering exponent λ=0, a parabolic band has

- n = N (2mk_BT)^(3/2) F₁/₂ / (2π²ℏ³),
- r_H = 3 F₁/₂ F₋₁/₂ / (4 F₀²),
- R_H = s r_H/(en), with s=+1 for holes and −1 for electrons.

Substitution gives 3π²ℏ³ F₋₁/₂ / [2e(2mk_BT)^(3/2)F₀²]. The code's multiplier
already contains (0.5+2λ)/(1+λ)² = 1/2; its additional denominator 2 was redundant.
For two independent channels the reference is the Putley sum
R_H = (R_H,1 σ₁² + R_H,2 σ₂²)/(σ₁+σ₂)².

`tests/test_hall_physics.py` evaluates the integrals by independent quadrature and
uses SciPy constants. It covers a suppressed second band, bipolar channels,
N₂/N₁=1 and 3, and acPh, dis and acPhDis. The relative tolerance is 1e−5; the
inherited Boltzmann constant differs from SciPy's. All 12 parameterised Putley
checks failed by a factor 0.5 before the correction and pass afterward. Two more
checks cover the limits r_H→1 and r_H→3π/8 and the SPB formula at a supplied
reduced potential. The separate SPB μ(T) issue (#103) is not addressed here.

The issue points to Supplementary Note 3 Eq. (12) of
[the SeeBand paper](https://doi.org/10.1038/s41524-025-01645-y), and warns that paper
Eq. (7) omits a factor 3. The derivation and numerical reference above are explicit;
the SI PDF could not be retrieved in this implementation session. Human physicist
confirmation remains outstanding and is not implied by passing tests.

## Regression results

Original desktop captures in `tests/fixtures/golden` remain byte-for-byte intact.
`tests/fixtures/physics/p2.json` records new web expectations for the affected
`dpb_see_res_hall_calc` and `dpb_see_res_hall_fit` calls, using the original inputs.
The replay test selects these expectations by the full call ID; every other call
still uses its original desktop expectation. Existing exclusions for unstable
`02_SiP` fits and bounds remain in force.

Regenerate from the repository root after the normal Python setup:

```sh
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/capture_p2_results.py
PYTHONPATH=packages/seeband_core/src uv run python packages/seeband_core/scripts/generate_demo_dataset.py
```

Replay on macOS arm64 with Python 3.13.18 and NumPy 2.5.4 gives:

| Example         | Scattering | Desktop m₁/mₑ | Corrected m₁/mₑ |
| --------------- | ---------- | ------------- | --------------- |
| 01_Fe2VAl09Si01 | acPh       | 5.996896      | 9.519479        |
| 01_Fe2VAl09Si01 | acPhDis    | 4.400645      | 6.985589        |
| 03_AWI32_SI     | acPh       | 1.236769      | 1.963248        |
| 03_AWI32_SI     | acPhDis    | 1.226563      | 1.947047        |

These are fits to the original measurements, not synthetic inputs. The masses
increase by about 2^(2/3)=1.587401, so density inferred from those masses increases
by about 2. Mass bounds can limit this relation. The synthetic demo is regenerated
with its original parameters and noise seed: Hall values double; S and ρ do not
change. Its obsolete Hall-prefactor flag is removed from the registry and demo.

#71's full desktop/web comparison and physicist review remain outstanding. #80 was
closed at the project owner's request; no author confirmation is recorded.
