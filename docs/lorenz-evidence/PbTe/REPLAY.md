# Replay and source retrieval

Run from this directory with Python and NumPy, SciPy, pandas and Matplotlib installed. PDF extraction additionally needs pypdfium2 (original Thesberg extraction: 5.15.2) and pdfplumber (Pei inset version in its metadata). SeeBand-dependent scripts need the pinned core and its declared dependencies. Use a disposable copy: scripts overwrite their adjacent CSV/JSON/PNG outputs. The baseline, partial conductivity and Kane comparison plots are bundled. Other plots can be regenerated.

## Source inputs

Download sources separately; no source PDF or image is bundled:

- [Thesberg published PDF](https://www.iue.tuwien.ac.at/pdf/ib_2017/JB2017_Thesberg_1.pdf), DOI [10.1103/PhysRevB.95.125206](https://doi.org/10.1103/PhysRevB.95.125206). SHA-256 `7ffa4787b6597d8bfbb9da7f746fcca9ea1fe6d372a77c8abf4517117eba7f19`. Figures 5–6: PDF page 8, printed 125206-8. PDF path indices and calibration require this exact PDF.
- [Pei 2011 supplementary PDF](https://authors.library.caltech.edu/records/r4cjr-qn161/files/nature09996-s1.pdf), DOI [10.1038/nature09996](https://doi.org/10.1038/nature09996). SHA-256 `cb11a4dd3add97537ca90be16cd25f92f849ae2e553a0edc8262dc87a0ca6578`. S3 is PDF page 2; mobility discussion is page 3. [Inset extraction notes](ref49/inset/extraction-notes.md) and [Hall reading coordinates](hall400/figure/pei-si-s3a-provenance.md) permit independent checks.
- [Nature Figure 3](https://www.nature.com/articles/nature09996/figures/3): [resistivity note](mobility400/resistivity/README.md) gives the exact publisher image URL, SHA-256, symbol selection and pixel calibration. Download the unchanged 946×374 image and recalculate the 400 K reading with the documented formula. No automated resistivity extraction script was present in the archive.
- [US9059364B2 disclosure](https://patents.google.com/patent/US9059364B2/en), [PDF](https://patentimages.storage.googleapis.com/62/cc/dc/5258554c629281/US9059364.pdf), pp. 15–17; [Pei later Kane equations](https://arxiv.org/pdf/1111.5355), Eqs. 2, 3, 6. Additional theory links are retained in each study README. Patent inputs are manually transcribed and interpreted, not automatically extracted.

Verify downloaded hashes before extracting and inspect important labels/notation against original page images. Source hashes are not evidence of permission to redistribute full source documents.

## Numerical replay using included digitizations

The independent audit, Kane, Hall, mobility and patent calculations below do not import production core:

```sh
python order700/order.py
python formula-audit/band_edge_bound.py
python formula-audit/direct.py
python formula-audit/source_plot.py
python kane/replay.py
python kane/mobility_audit.py
python hall400/check_s1.py
python hall400/band_factors.py
python mobility400/reverse.py
python patent400/compare.py
```

Saved `.txt` files are archived stdout; rerun commands print fresh diagnostics rather than overwriting those text records. The other scripts overwrite calculated tables and plots. `direct.py` compares 333 included density-scenario rows with independent quadrature, first with SciPy constants and then matching core constants. These checks verify selected assumptions and observables, not the physical applicability of the source models.

For core replay, install the core from [8c6fafcd54c090c37feae6265108b7d94a4d4570](https://github.com/pdasya/seeband-web/tree/8c6fafcd54c090c37feae6265108b7d94a4d4570), or place that checkout's `packages/seeband_core/src` on `PYTHONPATH` with its dependencies installed. Use Python 3.13 as recorded by the latest formula audit. The historical audit also checked [84af5de52675c45ebbc139ec517873c573a4effa](https://github.com/pdasya/seeband-web/tree/84af5de52675c45ebbc139ec517873c573a4effa) with identical baseline CSV bytes. Do not treat a replay against an arbitrary current revision as the pinned historical result.

```sh
python compare.py
python plot.py
python order700/order.py
python formula-audit/matched_mu.py
python ref49/replay.py
python ref49/infer_mu.py
python ref49/plot.py
```

The selected SPB check `python patent400/check_spb.py` instead records [9929fb4ffb04a93fcca2bfbce28548c58c61ad35](https://github.com/pdasya/seeband-web/tree/9929fb4ffb04a93fcca2bfbce28548c58c61ad35). Its 69 eta points span −5 to 12; the archived Kim L(S) approximation deviates by up to 3.652% relative to core, while the independent ionized-impurity Seebeck identity agrees to 1.024×10⁻⁹ µV/K. These are selected SPB checks, not a patent-model implementation in SeeBand.

## Optional source extraction

Replace the placeholder paths with downloaded source locations:

```sh
python digitize.py /path/to/THESBERG.pdf
python formula-audit/inverse_figures.py /path/to/THESBERG.pdf
python ref49/inset/extract.py /path/to/PEI_SI.pdf
```

`inverse_figures.py` imports `formula-audit/crosscheck.py`; this also regenerates `slices.csv` and `record.json` before `inverse.csv`. Re-run `band_edge_bound.py` after this extraction. Re-run the other computations to propagate any intentional digitization change. The extractor records the PDF path supplied at runtime; if sharing a regenerated metadata file, use a portable source name instead of a private absolute path.

The archived `ref49/crosscheck/record.json` preserves an earlier interpretation of the same Fig. 5 slices; its duplicate script and CSV were consolidated into `formula-audit/`. The baseline plot omits no source labels but cannot verify off-frame solid values. Source 850 K text estimates and sensitivity scenarios must not be treated as measured points or uncertainty intervals. Hall peak inversion assumes locally fixed mobilities, density and Hall factors; a temperature maximum alone does not prove those assumptions. Absolute deformation potentials depend on the adopted elastic normalization and sample correspondence.
