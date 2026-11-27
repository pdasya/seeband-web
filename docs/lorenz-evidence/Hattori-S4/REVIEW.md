# Hattori S4 · two parabolic valence bands with acoustic scattering

**Finding.** All 232 independently readable Lorenz ratios agree with the SeeBand core within the graphical reading envelopes. Seebeck has a reproducible discrepancy on the positive chemical-potential tail. This is a comparison against published model curves at 900 K. There are no experimental error bars or fitted parameters.

## What was compared

Hattori, Usui & Mizuguchi, [published article](https://doi.org/10.1016/j.mtadv.2026.100896), [published supplement](https://ars.els-cdn.com/content/image/1-s2.0-S2590049826002110-mmc1.docx), [arXiv PDF with Note 4 and Fig. S4 on pp. 45–46](https://arxiv.org/pdf/2603.21649#page=46). The published image and the PDF raster have identical RGB pixels on white. Calibration and traced pixel positions are in `figure/`. Source images and overlays are excluded; regenerate them locally using `figure/README.md`. Reading intervals account for line width, pixel spacing, local slope and merged traces. They are graphical envelopes rather than statistical intervals.

Panels d, e and f give conductivity, thermopower and open-circuit electronic thermal conductivity. Eleven heavy-band offsets span −0.5 to +0.5 eV in steps of 0.1 eV relative to the light-band maximum. Each has 55 common chemical potentials from −0.75 to +0.60 eV. The original native-column traces cover slightly wider panel-dependent ranges.

## Inputs and conventions

Table 1 supplies heavy/light relaxation-time prefactor ratio 0.375, valley counts 12/4 and mass ratio 5. The heavy per-valley mass is 0.34 free-electron masses. For γ = −0.5 the parabolic-band spectral conductivity is linear in distance below each edge. The heavy/light spectral prefactor ratio is 0.375 × (12/4) × √5 = 2.51558. In SeeBand's N B/M convention this gives B = 4.19263. The absolute scale uses Eq. (16), 30,000 S/m for the heavy band alone at μ − E_H = +0.060 eV, applied to the acoustic exponent. This continuation of the reference condition is an assumption because S4 does not restate the normalization. It gives A = 31,437.26 S/m. Overall normalization cancels in S and L.

The pinned core takes a density. At each prescribed μ the replay computes the equilibrium hole density for both bands and supplies it to the VB+VB solver. It checks recovery of μ to 1e−10 eV. The sweep thus follows the horizontal axis of S4. It does not describe a single sample heated at fixed doping.

## Evidence

| Quantity | Distinct readings | Inside reading envelope | Median absolute deviation from traced center |
| -------- | ----------------: | ----------------------: | -------------------------------------------: |
| σ        |               232 |                     232 |                                        1.42% |
| S        |               261 |                     231 |                                        1.43% |
| κ_el     |               356 |                     356 |                                        0.65% |
| L        |               232 |                     232 |                                        1.70% |

The denominator for each row is 605 sampled points. Neighboring readings on a raster are correlated. For L, calculate κ_el/(σT) from the source at the same ΔE and μ. Ratio bounds use κ_low/(σ_high T) and κ_high/(σ_low T). Among the remaining 373 points, 101 give finite bounds on unresolved strokes and 272 admit no finite upper bound because the conductivity interval reaches zero. One vertical pixel in panel d represents about 50,955 S/m. Never divide the representative centers of merged floor traces. At μ = −0.70 eV and ΔE = +0.30 eV the source gives L = 2.336 [2.171, 2.531] versus 2.386 from SeeBand, in units of 10⁻⁸ W Ω/K².

At ΔE = +0.10 eV and μ = +0.60 eV, S is 697.6 [685.3, 708.3] μV/K on the raster. SeeBand gives 738.94 μV/K. Independent inspection of the pale red line confirmed the discrepancy. Independent integration of the two linear spectral distributions reproduces all four core outputs over 3,201 points to a maximum relative difference below 8e−13. A sensitivity evaluation using ±10 kBT around μ gives 698.07 μV/K at this point. Removing the far-energy tail changes the mean transported energy when the valence edge lies well below μ. Eq. (2) in the article specifies infinite limits. The numerical cutoff used to produce the published figure is unknown. The diagnostic is separate from the benchmark prediction.

The same-sign band mixing term is w_L w_H (S_L − S_H)², with w_i = σ_i/σ. Adding it to w_L L_L + w_H L_H gives total L. Both bands transport holes. model.csv reports the intrinsic weighted term and the mixing term separately.

## Replay

Run from this directory. Stored CSVs and our comparison plots support review without downloading the paper. Source PDFs, raw figure rasters and overlays containing source figures are intentionally excluded. See `figure/README.md` for hash-checked source extraction and optional redigitization.

Use Python 3.13 or later to install the pinned core. The calculations below were rechecked with Python 3.12.7, NumPy 1.26.4, SciPy 1.15.2, pandas 2.2.3 and Matplotlib 3.10.0. The archived 3.12 comparison imported the pinned source directly. The installation below uses the supported Python and NumPy ranges declared by the package. This is a forward calculation, with no optimization or estimated parameter confidence intervals.

```sh
python -m venv .venv
. .venv/bin/activate
git clone https://github.com/pdasya/seeband-web.git
git -C seeband-web checkout --detach 84af5de52675c45ebbc139ec517873c573a4effa
python -m pip install ./seeband-web/packages/seeband_core pandas matplotlib pillow
python replay.py
python moments.py
python compare.py
python plot.py
```

`VALIDATION.md` records the rerun commands, numerical cross-checks and limitations. The full core revision above is the benchmark target even if this review is opened on a later project revision.

Open `all-offsets.pdf` for four panels at each offset, or `overview.png` for three representative offsets. `comparison.csv` contains source estimates, intervals, resolution flags and predictions. Only `trace_center` is suitable for center-based residuals. `per-offset-summary.csv` records coverage and deviations for each offset. The L plots clip bounds at the displayed scale; top ticks identify unbounded intervals.
