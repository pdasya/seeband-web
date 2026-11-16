"""The version of the installed package, and the commit it was built from."""

import os
import re
import subprocess
from importlib.metadata import version
from pathlib import Path

API_VERSION = version("seeband-api")

# The checkout this file sits in when it runs from source: apps/api/src/seeband_api/version.py.
_CHECKOUT = Path(__file__).resolve().parents[4]
# Git's own short form, so that a commit reads the same however it was found.
_SHORT = 12
_GIT_TIMEOUT_S = 2


def _short(commit: str) -> str:
    """A full hexadecimal hash cut to git's short form; anything else as it was given."""
    return commit[:_SHORT] if re.fullmatch(r"[0-9a-f]{13,40}", commit) else commit


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=_CHECKOUT,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_S,
        check=True,
    ).stdout.strip()


def _commit() -> str | None:
    """The commit, from `SEEBAND_COMMIT`, which an image sets as it is built, or from git.

    Git is asked only in this project's own checkout, with its `.git` beside `apps`, and only if
    git's top level is that checkout: an installed package inside some other repository, as a home
    directory kept in git, would otherwise report that repository's commit, which is worse than
    none. Uncommitted changes add `-dirty`, so that a file exported from them does not claim a
    commit it did not come from. With neither, the commit is unknown, and None says so.
    """
    chosen = os.environ.get("SEEBAND_COMMIT", "").strip()
    if chosen:
        return _short(chosen)
    if not (_CHECKOUT / ".git").exists():
        return None
    try:
        if Path(_git("rev-parse", "--show-toplevel")).resolve() != _CHECKOUT:
            return None
        head = _git("rev-parse", f"--short={_SHORT}", "HEAD")
        changes = _git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.SubprocessError):
        return None
    if not head:
        return None
    return f"{head}-dirty" if changes else head


API_COMMIT = _commit()
