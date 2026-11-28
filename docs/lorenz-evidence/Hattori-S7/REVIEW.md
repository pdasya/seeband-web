# Hattori supplementary figure 7: two-band Lorenz-number comparison

## Source and observable

Y. Hattori, H. Usui and Y. Mizuguchi, _Ideal band structures for high-performance thermoelectric materials with band convergence_. [Author PDF including supplement](https://arxiv.org/pdf/2603.21649#page=49). Supplementary Note 7, printed supplementary pages 11–12, PDF pages 48–49. Figure S7 is on PDF page 49. SHA-256 of the source PDF used for digitization: 1131f062bd5dca7915fe01ff72a0f2bba46ba0a836c860cb1ddcaf40535ef971.

Left panel, β = 1. β is the exponent of spectral conductivity in kinetic energy measured from the band edge. Both edges have equal prefactors, with the chemical potential at the valence edge. At fixed temperature, compare σ, |S|, and electronic open-circuit κ, each divided by its own finite-gap value at g = Eg/(kBT) = 10. The figure shows seven markers per series at g = 4 through 10. Curves connecting markers do not supply independent measurements at intermediate gaps. L/L₁₀ follows from the normalized κ divided by the normalized σ. S7 provides computed reference curves. It supplies neither an absolute experimental Lorenz number nor a reference value in SI units.

## Forward calculation

The replay uses SeeBand core [revision 84af5de](https://github.com/pdasya/seeband-web/tree/84af5de52675c45ebbc139ec517873c573a4effa), explicit VB+CB, joint S and resistivity mode, intraband acoustic scattering, equal masses, degeneracies, and amplitude weights. The common conductivity normalization A is one. This arbitrary scale cancels in every comparison. We use 900 K to express the dimensionless inputs. For each gap the net carrier density is calculated from the two parabolic DOS populations at μ = 0. The ordinary explicit DPB solver then recovers μ; the script checks this for every gap. Prescribing a single net density across this sweep would sample a different curve. No offsets or weights were adjusted to the plot. The source-independent integration in independent.py evaluates the first three moments of the total spectral conductance directly and checks all 28 normalized core outputs at the seven marker positions.

model.csv is a dense sweep with step 0.02. σ and κ raw columns use an arbitrary common conductivity amplitude, S is V/K and L is W Ω/K². Only the normalized columns are compared. comparison.csv gives central model minus digitized residuals, reading bounds, and a containment flag. A missing digitized point estimate stays blank. At the normalization gap the exact ratio is one by definition and provides no independent test. At other gaps the quotient interval is [κ_low/σ_high, κ_high/σ_low] using normalized source bounds. This is a conservative rectangle bound, with no assumption of independent Gaussian errors. Residuals are based on the exact integer parameter positions specified by the source markers. Digitization envelopes represent graphical reading precision, not experimental uncertainty or a target tolerance selected from the residuals.

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
python independent.py
python compare.py figure/s7_beta1_digitized.csv
```

`VALIDATION.md` records the rerun commands, numerical cross-checks and limitations. The full core revision above is the benchmark target even if this review is opened on a later project revision.

## Results

All 16 readable central marker values of σ, |S| and κ before the anchor agree within their reading envelopes. The four readable quotients also agree. σ is hidden at gaps 8 and 9; only geometric bounds are reported there for σ and L/L₁₀. At gap 10 all quantities equal one by definition. The largest relative center differences are 0.125% for σ, 0.124% for |S|, 0.195% for κ, and 0.191% for the reconstructed L ratio. These four statistics describe agreement of central readings, not the accuracy certified by the raster. The ordinate half-envelope is about 0.0202 for visible symbols, 0.0235 for partial overlaps. At gap 4 the reconstructed ratio is 1.7889 [1.7352, 1.8447], compared with 1.7912 from the core. At gaps 8 and 9 the bounds [0.9614, 1.0720] and [0.9622, 1.0496] both include one: the image alone cannot establish the small predicted excess. Model absolute L₁₀ is 1.6230 × 10⁻⁸ W Ω/K². The independent spectral-integral replay agrees with SeeBand to 3.42 × 10⁻¹² or better in all four normalized quantities. The result validates the normalized bipolar response for the published symmetric fixed-μ case.
