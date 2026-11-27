# Acoustic Kane reference

Lin and Liu provide the acoustic Kane moments and mass examples in Tables 1–2. With the SeeBand constants, 108 fixtures give a maximum relative difference in L of 3.08 × 10⁻¹³ between two implementations of the Kane transport distribution. At zero nonparabolicity 36 fixtures agree with the acoustic parabolic moments to 1.87 × 10⁻¹¹ in L. At fixed single-valley mass and reduced chemical potential, multiplying valley count N scales conductivity and leaves L invariant. These are design-equation checks. A production fit or an experimental measurement of L requires separate evidence. [Paper](https://doi.org/10.1038/s41598-022-09734-4)

The recorded output includes both mass tables, limiting cases and a numerical example. To reproduce, extract the three scripts from the pinned design revision in a separate directory. Use the review's installed core for constants.

```sh
git fetch origin 2bc068d306e0351c9357c97afa6e7825f7934840
git archive 2bc068d306e0351c9357c97afa6e7825f7934840 scripts/verify_skb_design_reference.py scripts/verify_band_composition_design.py scripts/verify_spb_design_coefficients.py | tar -x
python scripts/verify_skb_design_reference.py --core
```
