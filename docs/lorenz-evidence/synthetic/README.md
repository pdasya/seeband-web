### Reproduction of the reported peak

The attachment describes the synthetic legacy DPB example (VB + CB, acPh, N₁ = N₂ = 1), with 50 points from 50 to 800 K. Its former export contains both SI and normalized columns. The largest sampled total is at 371.428571 K.

| Quantity                              |                   Value |
| ------------------------------------- | ----------------------: |
| Band 1, band 2 conductivity fractions |      0.724936, 0.275064 |
| Band 1, band 2 Seebeck coefficients   | +245.406, −312.738 μV/K |
| Own band Lorenz numbers               |      1.564686, 1.521571 |
| Conductivity-weighted band term       |                1.552827 |
| Electron–hole heat transport term     |                6.211932 |
| Total model Lorenz number             |            **7.764759** |

Lorenz values in the table are in 10⁻⁸ W Ω K⁻². For two independent conducting bands, the total under open-circuit conditions is w₁L₁ + w₂L₂ + w₁w₂(S₁ − S₂)², wᵢ = σᵢ/Σσ. The model predicts electronic thermal conductivity via κₑ = LσT. The old plotted value 3.178365 is the same peak divided by the Sommerfeld value. This numerical check establishes the prediction of the model for these inputs. The example is synthetic.

At 50 K, the sampled maximum and 800 K, an independent 40-digit polylogarithm calculation solves carrier balance and recomputes the moments. The pre-change core agrees to within 7×10⁻¹⁴ relative. At all 50 temperatures the pre-change HTTP API reproduces the three absolute columns within 2.5×10⁻¹² relative using the rounded exported parameters.

Run `python peak.py` against the pinned core. Run `python api_replay.py` in a SeeBand API development environment to compare the original export at all 50 temperatures via the FastAPI test client.
