#!/usr/bin/env bash


# Check for both pyvenv and normal venv environments
# https://www.python.org/dev/peps/pep-0405/
if python3 -c 'import os, sys; sys.exit(0) if "VIRTUAL_ENV" in os.environ else sys.exit(1)' >/dev/null 2>&1
then
    # inside virtual env
    python3 setup.py -q develop --upgrade
else
    python3 setup.py -q develop --user --upgrade
fi
