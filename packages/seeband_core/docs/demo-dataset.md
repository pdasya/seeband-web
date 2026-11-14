# Demo dataset

`demo_dataset.load_demo_dataset` gives visitors without data something to fit. **It is synthetic.** It comes from the DPB model of this project with added noise, and it is not a measurement of any material. A client must say so: `synthetic` is always true, and `message_key` gives the text through i18n.

## What it holds

| Item       | Value                                                                            |
| ---------- | -------------------------------------------------------------------------------- |
| Model      | DPB, S + ρ + R_H, `acPh`                                                         |
| Parameters | m_eff = 1.2, band gap = 800 K, Fermi energy = -150 K, A = 60000, B = 1, m1 = 1.4 |
| Data       | 31 points from 50 to 800 K, of S, ρ and R_H                                      |
| Noise      | seed 2026: 1 µV/K on S, and 0.5% on ρ and R_H                                    |

S peaks at about 207 µV/K near 175 K. From there to 300 K it falls mostly because band 2 gains conductivity, from 1.9% to 20.5% of the total. B = 1 keeps a DPB S fit the same model as the rest, because that fit has no B.

R_H uses the corrected DPB Hall prefactor from P2 (#81). The demo was regenerated with the same seed and relative noise: R_H doubles at fixed parameters, while S and ρ are unchanged. Its `known_issues` list is empty.

## What a fit gets from it

Fits start from `default_start`. Note that this has B = 1, its true value. On one Mac:

| Mode                                             | Result on the stored data                                                                                                                                                                 |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DPB S, DPB S + ρ and DPB S + ρ + R_H with `acPh` | Recover the parameters, with the largest errors at B -0.60%, m_eff -0.26%, A -0.14%, E_F +0.12% and m1 +0.07%. RMSE matches the noise: 0.8 µV/K in S and 0.5% in ρ and R_H                |
| DPB with `dis`                                   | Runs, with E_F and m1 within 1%, but m_eff off by 31% and the gap by 11%. G ends at its bound, and the RMSE of ρ is 88%: the wrong scattering type shows there                            |
| DPB with `acPhDis`                               | After P5, both iterative modes converge in 3 iterations, with m_eff off by 23% and the gap by 8%. B, C and D end at their bounds; the wrong-scattering fit remains unsuitable             |
| SPB S, default start                             | Gives the wrong sign, with E_F at its bound of 3000 K. The default mass of this mode is +1.01, for an n-type band, and the data are p-type. A client should start it with a negative mass |
| SPB S with mass -1 and E_F -100 K, and SPB S + ρ | Run, with an RMSE of 90 µV/K: one band cannot describe this data. With `acPhDis`, C ends at its bound                                                                                     |
| SPB S + ρ + R_H                                  | `failed`, as this mode does with a default start (D3). It is disabled                                                                                                                     |

**These errors are one draw of the noise, not what the fit achieves in general.** The margins in the tests hold for the stored data. In an independent review over 150 other seeds, S + ρ + R_H had median errors of 1.56% in B, 0.56% in m_eff and about 0.3% in the others, with a worst case of 6.6% in B. 105 of the 150 missed a margin. A start of B = 0.95 or 1.05 also changes the result, because the loop stops after 2 iterations (the broader stopping rule remains tracked in #176; P5 repairs the separate mixed-scattering early exit).

## Interpolation

With interpolation on over 50 to 800 K, `extrapolated` stays false and these fits still recover the parameters. The polynomial still changes the data: R_H is off by up to 29% near 779 K, ρ by 2.5% and S by 2 µV/K. A range beyond 50 to 800 K sets `extrapolated`.

## For FS11

- The design's demo differs: S and ρ only, over 25 to 800 K, with uniform noise, r = 0.6, E_g = 500 K, E_F = 650 K and B = 1.5, which is outside the fit bounds of 0.9 to 1.1, and S negative. Its labels need changing.
- `demo_table_text` gives it as the text of a file, with the headers `T`, `S`, `rho` and `R_H`, because the parser does not read the keys of the stored file. It reads back exactly, with no warnings. `GET /api/demo` serves that result.

## Regenerating

The stored file is what users get, so its numbers do not depend on the machine, and a test pins its hash. Another test checks that the generator still gives the same data within 1e-9 of each column's largest value. The stream of `default_rng` has no guarantee across numpy versions, so an update could fail that test without any real change. Regenerating on other library versions changes bytes in the last digits (6.7e-16 relative). After a change to the model, run this and update the pinned hash, and expect the recovery margins to need another look:

```sh
uv run python packages/seeband_core/scripts/generate_demo_dataset.py
```
