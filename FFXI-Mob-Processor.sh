#!/bin/sh
# Portable launcher: activate your virtual environment before running.
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -B "$BASE/mob_processor.py" "$@"
