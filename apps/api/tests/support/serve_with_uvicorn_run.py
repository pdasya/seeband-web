"""Starts the leaky app with `uvicorn.run(app)`, the way a script might."""

import sys

import uvicorn
from leaky_app import create_app

uvicorn.run(create_app(), port=int(sys.argv[1]))
