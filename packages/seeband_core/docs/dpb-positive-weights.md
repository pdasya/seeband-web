# Positive longitudinal DPB weights (P13)

P13 corrects the longitudinal two-band transport weights while retaining band
1 as valence, the signed public mass ratio R = m₂/|m₁|, and r = R/N for
N = N₂/N₁. The sign continues to determine carrier type in occupations,
conserved density and carrier signs. Longitudinal transport weights use |r|.

For the signed single-valley mass convention, the longitudinal weights are:

| DPB scattering mode | Band-2 weight relative to band 1 |
| ------------------- | -------------------------------- |
| S-only              | 1/\|r\|                          |
| single scattering   | B/\|r\|                          |
| mixed scattering    | B(C_K + T)/((D_K + T)\|r\|)      |

Here B is the relative scattering factor for the selected mode; in mixed
scattering C_K = 300 K × C and D_K = 300 K × D, with T in kelvin. These
weights propagate through Seebeck, electrical conductivity, resistivity,
electronic thermal conductivity and per-band contributions. The longitudinal
conductivities remain positive for valid positive channel factors. Hall keeps
the signed carrier contributions and uses the corrected resistivity.

## Fit branch

Each DPB fit keeps the carrier branch selected by its signed initial mass.
Zero is excluded, and user/model bounds are intersected with that branch;
there is no artificial mass floor. Density solving, fit objectives and
tolerances are unchanged. Existing numerical failures within the valid domain
remain explicit.

## Limits and evidence

The equal-band limit for identical valence bands with equal scattering has
conductivity and electronic thermal conductivity twice the single-band value,
the same Seebeck coefficient, and half its Hall coefficient. This is a
synthetic limiting check, not a measurement.

The following synthetic comparisons were independently reproduced by the parent
and the implementation's focused tests pass. They used Python 3.13.18,
NumPy 2.5.4 and SciPy 1.18.1 environment, synthetic T = 300 K, E_F = −500 K,
E_g = −200 K, N = 1, and compare the previous S-only weight with P13:

|    r | Previous S (µV/K) |   P13 S (µV/K) |
| ---: | ----------------: | -------------: |
| -1.0 |     88.7101086635 | 170.0882684141 |
| -0.5 |    292.1015685857 | 171.9177888016 |

At r = −1 and E_g = 0, the old expression returned NaN while P13
gives S = 148.9913091568 µV/K with the same signed density roots.
These synthetic values are not evidence that neural guesses are valid across
the corrected valence–valence branch.

P13 removes `negative_m_eff_weight`, but does not resolve the iterative
nonunit-degeneracy bounds issue (#85), fit identifiability (P16), general fit
reliability (P19), or numerical underflow. P18 explicit band types and CB+CB
remain deferred. Human physicist confirmation and desktop parity are separate
release gates. The physical source for the positive longitudinal factors is
[SeeBand: a highly efficient, interactive tool for analyzing electronic transport data, Eqs. 1–3 and 11](https://arxiv.org/html/2409.06261v2).

## Recorded fit regressions

`tests/fixtures/physics/p13.json` records all 24 historical DPB fitting calls
under the new branch constraint. `scripts/capture_p13_results.py` reproduces
them and pins hashes of the unchanged P8 and P11 captures. These are
implementation regressions, not independent experimental validation.

All previously converged calls for examples 01 and 03 still converge. Their
parameters and some iteration counts can change because intersecting the
bounds changes the optimizer trajectory even on a positive branch. All eight
DPB calls on example 02 (Si:P), including the auxiliary disorder call, now
fail at the existing evaluation budget. Seven previously reported convergence
with collapsed parameters; the remaining historical disorder call failed its
bounds check. The budget, objective and tolerances have not been relaxed.
This is an explicit fit failure, not a repaired fit to Si:P; general numerical
reliability remains P19. Physical limiting tests independently check the
transport correction rather than treating these fit regressions as proof.

The historical auxiliary D1 fit for example 01 also collapses after branch
restriction. Mac and Linux return different scattering parameters and rho
residuals (approximately 100% and 81.4%). On the owner's explicit decision,
this already unreliable case has a diagnostic compatibility contract rather
than numeric F/G or post-fit rho agreement. Stable band comparisons, finite
values, recorded bounds, status/message, both known-issue flags and the mass
boundary remain checked. See [platform evidence and limits](golden-results.md).
No data, estimator, solver tolerance or production formula was changed to
force a credible fit; the underlying optimizer reliability remains P19.
