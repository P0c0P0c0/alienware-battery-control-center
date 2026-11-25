#!/bin/sh
set -eu
cd "$(dirname -- "$0")/.."
root=$(pwd)
python=/usr/bin/python3
(cd backend && "$python" -B -m unittest discover -v)
PYTHONPATH="$root" "$python" -B -m unittest discover -s tests -v
if [ "${1:-}" != "--core-only" ]; then
    (cd dashboard && "$python" -B -m unittest discover -v)
fi
