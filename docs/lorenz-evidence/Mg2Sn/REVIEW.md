# Replaying Naithani et al. on Mg₂Sn with SeeBand

**Result.** Published acoustic two-parabolic-band curves are reproduced for both doping polarities. On readable parts of Figure 3, mean absolute errors per sample are 0.29–1.28 µV/K in Seebeck (nine traces) and 0.25–2.72% in resistivity (eight independently readable traces). The low-doped n-type conductivities overlap. The published curve for Sc0.05Mg1.95Sn cannot be isolated with confidence. Its model prediction and four identifiable experimental conductivity symbols are available separately.

## Source and scope

H. Naithani, E. Müller and J. de Boor, _Developing a two-parabolic band model for thermoelectric transport modelling using Mg₂Sn as an example_, J. Phys. Energy 4, 045002 (2022). [DOI](https://doi.org/10.1088/2515-7655/ac7fb8) · [DLR record](https://elib.dlr.de/193456/). Download the published PDF from the DLR record for optional re-digitization. Tables 1 and 2 appear on printed page 7 (PDF page 8), Figure 3 on printed page 8 (PDF page 9). Full PDF SHA-256: b068909f3fccb9a49288816bc467f99282406b9def131dc60fc59f702ebe0116.

SeeBand revision [9929fb4](https://github.com/pdasya/seeband-web/commit/9929fb4ffb04a93fcca2bfbce28548c58c61ad35). The experiment exercises the explicit VB+CB core in joint S and resistivity mode with acoustic phonons. A caller supplies the published gap point by point. This verifies the numerical kernel for these inputs. The browser's scalar gap control was outside this experiment.

## Inputs and mapping

Both observables share the same parameters for a sample. For VB, CB respectively, the total DOS masses are 1.1 and 2 electron masses, valley degeneracies 2 and 3, and acoustic deformation potentials 9.5 and 6.7 eV. Material density is 3590 kg/m³ and sound speed 4800 m/s. The single-valley mass is the DOS mass divided by valley degeneracy to the power 2/3. The absolute VB mass in the core is 0.69295658 electron masses and the CB/VB single-valley mass ratio is 1.38753242. From the published mobility normalization (Eqs. 2–12), the core acoustic amplitude is 64982.99457 S/m, and B = (9.5/6.7)² = 2.01047004. See pref() in replay.py for the dimensional calculation. Table 2 gives the magnitude of the fixed extrinsic density. Each temperature has its own chemical potential solved at fixed n−p. samples.csv gives the sign convention by carrier type and densities in units of 10²⁰ cm⁻³. The paper flags n3, n4 and p4 densities as fitted. All nine are copied without adjustment here.

## Gap experiment

Temperatures 300 to 750 K at 5 K spacing. The published gap is (0.28 − 0.0002 T/K) eV. The control uses its 300 K value 0.22 eV at every temperature. All other inputs are identical. For undoped Mg₂Sn, the model's Seebeck zero lies at 583.7 K (linear interpolation of the grid). The orange model stroke on Figure 3(c) crosses at about 583 ± 8 K. With the fixed gap the crossing is 706.9 K. At 650 K the two predictions give −10.69 and +8.93 µV/K respectively, with resistivities 2.260 and 3.961 mΩ cm. This is a counterfactual gap sensitivity calculation. The symbols in the figure, the paper's model line, and this fixed-gap control are three distinct comparisons.

## Comparison and uncertainties

See comparison-S.png and comparison-rho.png. Solid blue is SeeBand with the paper's gap; dashed orange uses the fixed gap. Crosses sample the published 2PB curve; circles show identifiable experimental symbols. Full pixel-coordinate comparisons, including regions only partly visible, are in compared-points.csv. Figure 3(b,d) plots conductivity. Conversion: resistivity in mΩ cm = 1000 / conductivity in S/cm. Panel (b) has a broken axis. A ±19 S/cm reading envelope is important at low conductivity; converting to resistivity gives asymmetric uncertainty. Curve pixels are correlated. Each error statistic describes only the retained temperatures for that sample, without extrapolation. The mean errors are neither a precision specification nor an experimental goodness-of-fit test. The separate 54-point independent quadrature check in replay.py compares equations at 300, 500 and 750 K for both gaps and all samples. Maximum absolute difference in S is 1.01 × 10⁻¹⁰ µV/K and maximum relative resistivity difference is 1.64 × 10⁻¹³.

Against readable experimental symbols, the two lightly doped n-type samples give mean absolute S errors of 19.6 and 22.5 µV/K, and undoped Mg₂Sn gives 28.1 µV/K. Agreement with the paper’s computed curves is substantially closer. See metrics.csv for counts, covered temperature ranges and residuals for each available comparison. Where symbols overlap lines or each other, the readable subset can systematically favor separated observations. It cannot be assumed representative of the complete measurements.

## Replay

Use Python 3.13 and run from this directory. Access to the indicated SeeBand revision is required for the core replay. The digitization and comparison stages can also be run independently using the source PDF and bundled CSVs.

```sh
git clone https://github.com/pdasya/seeband-web.git seeband-web
git -C seeband-web checkout --detach 9929fb4ffb04a93fcca2bfbce28548c58c61ad35
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install ./seeband-web/packages/seeband_core pandas matplotlib pillow pypdfium2
# Download the paper from the DLR record as Naithani-2022.pdf for this optional step.
python figure/digitize.py Naithani-2022.pdf
python replay.py
python report.py
```

predictions.csv uses T in K, Eg_eV in eV, S in µV/K, rho in mΩ cm, sigma in S/cm. metrics.csv uses µV/K for S, percent relative to the digitized resistivity for rho. The fixed_MAE column applies the same metric to the fixed-gap control. See figure/README.md for source-image calibration, trace selection and digitization envelopes. replay-result.txt records the independent quadrature check.
