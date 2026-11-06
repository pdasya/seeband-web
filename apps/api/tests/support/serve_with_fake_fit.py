"""Runs `python -m seeband_api` with the fit `fake_<FAKE_FIT>` of `fit_functions`.

Real fits end on their own, and how long they take depends on the machine, so they cannot show
what happens to a fit that is still running.
"""

import os

import fit_functions
import seeband_api.fit
from seeband_api.__main__ import main

seeband_api.fit.run_fit = getattr(fit_functions, f"fake_{os.environ['FAKE_FIT']}")

if __name__ == "__main__":
    main()
