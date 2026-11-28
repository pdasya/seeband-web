# Curation validation

Performed on 2026-11-27 in a disposable copy of this package. Archived CSV and text evidence was not replaced by new outputs. This records focused collection checks; it does not repeat source inspection or the historical pinned-core runs.

- Python AST parse: all 21 retained scripts parsed successfully.
- Independent replay, Python 3.9.6 / NumPy 2.0.2 / SciPy 1.13.1: `python formula-audit/band_edge_bound.py`, `python formula-audit/direct.py`, `python hall400/band_factors.py`, `python mobility400/reverse.py`, `python patent400/compare.py` all exited 0, including their internal assertions.
- `direct.py`: 333 density-scenario points; maximum Lorenz difference from saved core output was 6.674×10⁻⁶ in units of 10⁻⁸ W Ω K⁻² with this environment's SciPy constants, and 7.683×10⁻¹⁴ after matching core constants. Maximum chemical-potential difference with matched constants was 2.776×10⁻¹⁵ eV.
- `python order700/order.py` passed using a separate existing runtime with NumPy 2.3.5 and pandas 2.2.3. It regenerated `budget-700K.csv` byte for byte. Totals were 1.97837, 1.82354, 1.76550 at increasing nominal doping; source totals were 1.88827, 1.93038, 2.02823 in the same Lorenz units.
- Recomputed edge-bound CSV has maximum absolute numeric difference 1.333×10⁻¹⁴ from the archived table. Patent CSV has maximum numeric difference 8.621×10⁻⁷ cm²/(V s), in light-hole mobility; this replay uses a different SciPy/constants environment. These are fresh-replay differences, not changes to the archived outputs.
- Portable-path scan, local Markdown link check, allowed-file-type check and canonical input existence checks passed. No private absolute paths, full source PDFs, source images, ZIPs or bytecode are included.

Not rerun here: the pinned-core-dependent comparisons, PDF extraction, visual source verification, and scripts importing Matplotlib. The available existing environments split NumPy/SciPy from pandas and lack Matplotlib; neither environment supplies the complete replay stack. The archive's exact core revisions and source extraction evidence are preserved, but were not independently revalidated in this curation. Install the documented dependencies and obtain source PDFs separately for a complete replay. No dependency or application change was made. No repository-wide `pnpm check` was run; validation ownership remains with the parent.
