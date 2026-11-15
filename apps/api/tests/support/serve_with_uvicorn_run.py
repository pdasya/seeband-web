"""Starts the leaky app with `uvicorn.run(app)`, the way a script might.

The guard is needed by any script whose app starts processes other than by `fork`: each child sets
up the main module again, and without it would start a server of its own. Before A16 this script
had none, and each pool worker did start one, but slowly enough that the test had read the log
before their tracebacks came.
"""

import sys

import uvicorn
from leaky_app import create_app

if __name__ == "__main__":
    uvicorn.run(create_app(), port=int(sys.argv[1]))
