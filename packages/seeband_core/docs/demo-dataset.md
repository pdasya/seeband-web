# Demo dataset

`demo_dataset.load_demo_dataset` gives visitors without data something to fit. **It is synthetic.** It comes from the DPB model of this project with added noise, it is not a measurement of any material, and a client must say so. `synthetic` and `description` carry this.

## What it holds

| Item       | Value                                                                            |
| ---------- | -------------------------------------------------------------------------------- |
| Model      | DPB, S + ρ + R_H, `acPh`                                                         |
| Parameters | m_eff = 1.2, band gap = 800 K, Fermi energy = -150 K, A = 60000, B = 1, m1 = 1.4 |
| Data       | 31 points from 50 to 800 K, of S, ρ and R_H                                      |
| Noise      | seed 2026: 1 µV/K on S, and 0.5% on ρ and R_H                                    |

S peaks at about 207 µV/K near 175 K, and falls as band 2 fills, so two bands show clearly.

R_H comes from the current model, so it carries the known error of the DPB prefactor (P2). The stored data stay as they are until P2. Then regenerate them, and record that in the changelog.

## What a fit gets from it

Fits start from `default_start`. On one Mac:

| Mode                                             | Result                                                                                          |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| DPB S, DPB S + ρ and DPB S + ρ + R_H with `acPh` | recover the parameters: m_eff and B within 1%, the rest within 0.5%                             |
| DPB with `dis` or `acPhDis`                      | run, but do not recover them. Parameters end at bounds, because it is the wrong scattering type |
| SPB S and S + ρ                                  | run, but one band cannot describe it. SPB S ends with E_F at its bound                          |
| SPB S + ρ + R_H                                  | `failed`, as this mode does with a default start (D3). It is disabled                           |

So a demo that only shows a good fit should use `acPh`, and the others show what a poor choice looks like.

## Regenerating

The stored file is what users get, so its numbers do not depend on the machine, and a test pins its hash. Another test checks that the generator still gives the same data within 1e-9 of each column's largest value. After a change to the model, run this and update the pinned hash:

```sh
uv run python packages/seeband_core/scripts/generate_demo_dataset.py
```
