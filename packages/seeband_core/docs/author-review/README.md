# Author review packet (P1, #80)

Draft for the project owner, prepared on 2026-11-12 against web revision
`c208925b31b896252aa48e2a54da964e2d0f76a9`. Contact has not been made.
All author responses are **unanswered**. This means no response has been recorded;
it does not mean that a message was sent or a deadline expired.

The desktop reference is `803b0e7a425a0a3f4f59688df77e3ad283ca49a1`.
The calculations are ported from SeeBand by Michael Parzer and Alexander Riss;
see the package LICENSE and root NOTICE. This packet changes no production formulas.

## Reproduce the first four observations

From the repository root, after the normal Python workspace setup:

```sh
PYTHONPATH=packages/seeband_core/src uv run python scripts/reproduce_author_findings.py
```

The script uses synthetic inputs, writes JSON to stdout, and captures numerical
warnings. [Recorded output](evidence.json) includes the environment and source revision.
It calls this checkout's core, not the desktop GUI. The complete desktop/web
comparison in [#71](https://github.com/pdasya/seeband-web/issues/71) remains open;
these probes do not replace it. Values below are observations on this revision.

| Finding    | Location in `src/seeband_core/math_module.py`                              | Input                                                                                   | Expected relationship                                                                                                                               | Actual result                                                                  |
| ---------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| P11 / #102 | `dpb_see_vs_temp_double_scatter`, `dpb_indCont_see_vs_temp_double_scatter` | m_eff=1, gap=300 K, E_F=−100 K, N=1, B=1, C=150 K, D=600 K; grids [300] and [300,800] K | S(300 K) independent of grid; sum of band contributions equals total                                                                                | 94.381907 µV/K alone and in band sum; 63.523744 µV/K on wider grid             |
| P14 / #105 | `fdint_robust`                                                             | order=0, eta=−40 K, T=1 K                                                               | F₀=log(1+exp(−40)), evaluated stably                                                                                                                | 0; stable reference 4.248354255291589e−18                                      |
| P16 / #107 | `dpb_see_vs_temp`                                                          | m_eff=1, gap=600 K, N=1, T=300 K; E_F=100 and 500 K                                     | At this temperature, equal values in the stated symmetric model do not distinguish these in-gap E_F values; this is not evidence of a formula error | Both give S=0 µV/K at 300 K; curve evidence and fit diagnostics remain pending |
| P8 / #87   | `dpb_chemPot_vs_temp`                                                      | m_eff=1.01, gap=1000 K, N=1, T=50 K; E_F=0 and −1e−6 K                                  | Intrinsic solution continuous at E_F=0                                                                                                              | μ=0 versus 499.626857 K; solver progress warning recorded                      |

C and D above are the low-level function's temperature-scale inputs. They correspond
to dimensionless 300 K ratios 0.5 and 2. Do not pass 0.5 and 2 directly when comparing
this run with the issue's example.

## Findings and response register

Every link below identifies the detailed finding, source locations and proposed work.
“Pending” evidence needs a fresh reproduction or primary-source review before the
owner presents it as verified. Issue-reported results have not been relabelled as
fresh measurements. A local reproduction does not count as author confirmation.

| ID / issue                                                     | Question for authors                                                                                                                   | Evidence in this packet                                                                                                                                     | Author status |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| [P2 / #81](https://github.com/pdasya/seeband-web/issues/81)    | Should the DPB Hall prefactor recover the SPB one-band Hall factor?                                                                    | Pending; issue reports factor 0.5 in DPB                                                                                                                    | unanswered    |
| [P3 / #82](https://github.com/pdasya/seeband-web/issues/82)    | What common scale should acPhDis C and D use in ρ, σ and κ?                                                                            | Pending; issue reports σρ≠1                                                                                                                                 | unanswered    |
| [P4 / #83](https://github.com/pdasya/seeband-web/issues/83)    | Confirm initial E, mass and returned B scaling for SPB S+ρ+R_H?                                                                        | Pending; desktop mode fails, see golden-results.md                                                                                                          | unanswered    |
| [P5 / #84](https://github.com/pdasya/seeband-web/issues/84)    | Must both parameter groups converge, with finite changes and safe zero handling?                                                       | Pending; issue and golden-results.md record early stops                                                                                                     | unanswered    |
| [P6 / #85](https://github.com/pdasya/seeband-web/issues/85)    | Confirm m_eff and degeneracy definitions shared by fit and chart?                                                                      | Pending; issue reports mismatch at N=3                                                                                                                      | unanswered    |
| [P7 / #86](https://github.com/pdasya/seeband-web/issues/86)    | Is fitting polynomial extrapolation beyond the measurements intentional?                                                               | Pending; desktop `seeband.py:3377` cited in issue                                                                                                           | unanswered    |
| [P8 / #87](https://github.com/pdasya/seeband-web/issues/87)    | Confirm carrier-balance root and explicit failure reporting at E_F=0?                                                                  | Reproduced above; grid-order cases still pending                                                                                                            | unanswered    |
| [P9 / #88](https://github.com/pdasya/seeband-web/issues/88)    | Should network selection use actual temperature extrema and sorted inputs?                                                             | Pending; desktop `neural_nets.py:21` cited in issue                                                                                                         | unanswered    |
| [P11 / #102](https://github.com/pdasya/seeband-web/issues/102) | Confirm temperature-specific band weights in acPhDis S?                                                                                | Reproduced above                                                                                                                                            | unanswered    |
| [P12 / #103](https://github.com/pdasya/seeband-web/issues/103) | Should SPB Hall integrals use μ(T) rather than E_F(0)?                                                                                 | Pending; issue records Hall-factor comparison                                                                                                               | unanswered    |
| [P13 / #104](https://github.com/pdasya/seeband-web/issues/104) | What band combinations are supported when m_eff<0, and should each conductivity weight be positive?                                    | Pending; requires physical interpretation                                                                                                                   | unanswered    |
| [P14 / #105](https://github.com/pdasya/seeband-web/issues/105) | Confirm stable Fermi-integral and ratio evaluation at extreme reduced potential?                                                       | F₀ reproduced above; other orders and ratios pending                                                                                                        | unanswered    |
| [P15 / #106](https://github.com/pdasya/seeband-web/issues/106) | How should zero-carrier/no-root parameter regions be represented?                                                                      | Pending; distinguish model domain from solver failure                                                                                                       | unanswered    |
| [P16 / #107](https://github.com/pdasya/seeband-web/issues/107) | How should in-gap E_F identifiability and the m_eff=0 singularity be reported?                                                         | Equal 300 K values reproduced above; this symmetric-model equality is consistent with in-gap nonidentifiability. Curve evidence and fit diagnostics pending | unanswered    |
| [P17 / #108](https://github.com/pdasya/seeband-web/issues/108) | What are the intended k/E units and band-2 curvature mass?                                                                             | Pending; `parabolic_band` and degeneracy need interpretation                                                                                                | unanswered    |
| PH-07 / #80                                                    | Please clarify paper Eq. (7)'s factor 3 versus Eq. (10) and SI (12),(17), the hole sign in SI (14), and carrier signs in SI (12),(13). | Reported by independent review in #80; primary PDFs still to verify                                                                                         | unanswered    |
| DATA / #80 comment                                             | What are the sources, citations and redistribution terms of `data/Examples`? May fixtures and walkthroughs include them?               | Root NOTICE records missing provenance; contact question only                                                                                               | unanswered    |

## Owner handoff and reply handling

1. Complete #71 and have a group physicist review pending evidence and the interpretation
   questions. Attach reproducible inputs, expected relationships and outputs for each
   additional verified finding. Check the paper and SI directly for PH-07.
2. Review [the email draft](email-draft.md). The contact in the pinned desktop
   [ReadMe.txt](https://github.com/xAngelswordx/SeeBand/blob/803b0e7a425a0a3f4f59688df77e3ad283ca49a1/ReadMe.txt)
   is `Michael_parzer@yahoo.de`. The project owner sends the message.
3. Record the actual sent date and message reference here. Proposed waiting period:
   14 calendar days from sending, one follow-up, then 7 more days. This is a proposal,
   with no active deadline. The owner must name the deciding physicist before sending.
4. For each reply, record date, finding IDs, exact response reference, interpretation
   and deciding physicist. Change status to `confirmed` or `rejected` only when the
   author explicitly supports that classification; ambiguous replies stay `unanswered`.
5. Link each decision and evidence in the corresponding P2–P9 and P11–P17 issue.
   After the waiting period, unanswered findings remain unanswered; record the group
   physicist's separate decision rather than attributing agreement to the authors.
6. Offer reviewed fixes and reproduction tests to the desktop project. Record the
   upstream offer/PR URL when it exists; this packet is not an upstream submission.

| Contact record                 | Value                               |
| ------------------------------ | ----------------------------------- |
| Sender                         | Project owner; named sender pending |
| Deciding physicist             | Pending owner designation           |
| Sent date / message reference  | Not sent                            |
| Follow-up / final review dates | Not scheduled                       |
| Replies / upstream offers      | None recorded                       |

#80 was closed on 2026-11-12 at the project owner’s request. This packet remains local;
no message was sent and no author confirmation was recorded.
