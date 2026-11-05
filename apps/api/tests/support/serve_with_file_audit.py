"""Runs the API, recording every file opened for writing, in the server and in its workers.

A listing of a folder cannot see a file deleted at once, or an anonymous temporary file. The audit
hook sees them all. Workers import this module again, so they install it too.
"""

import os
import sys

_FLAGS_THAT_WRITE = os.O_WRONLY | os.O_RDWR | os.O_CREAT
_log = os.open(os.environ["FILE_AUDIT_LOG"], os.O_WRONLY | os.O_APPEND | os.O_CREAT)


def _record(event: str, args: tuple[object, ...]) -> None:
    if event in {"tempfile.mkstemp", "tempfile.mkdtemp"}:
        os.write(_log, f"{event} {args[0]}\n".encode())
    elif event == "open":
        path, mode, flags = args
        writes = isinstance(mode, str) and any(letter in mode for letter in "wax+")
        if writes or (isinstance(flags, int) and flags & _FLAGS_THAT_WRITE):
            os.write(_log, f"open {path}\n".encode())


sys.addaudithook(_record)

if __name__ == "__main__":
    from seeband_api.__main__ import main

    main()
