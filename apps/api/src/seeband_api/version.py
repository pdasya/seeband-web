"""The version of the installed package, and the commit it was built from."""

import os
import subprocess
from importlib.metadata import version
from pathlib import Path

API_VERSION = version("seeband-api")


def _commit() -> str | None:
    """The commit, from `SEEBAND_COMMIT`, which an image sets as it is built, or from git.

    Git answers only in a checkout, as in development, where uncommitted changes add `-dirty`, so
    that a file exported from them does not claim a commit it did not come from. With neither, the
    commit is unknown, and None says so rather than a made-up value.
    """
    chosen = os.environ.get("SEEBAND_COMMIT", "").strip()
    if chosen:
        return chosen
    here = Path(__file__).resolve().parent
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        changes = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return f"{head}-dirty" if changes else head or None


API_COMMIT = _commit()
