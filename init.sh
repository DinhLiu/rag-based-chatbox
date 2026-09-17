#!/bin/sh
set -eu
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.10+ is required for the harness.' >&2; exit 3; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 3)'
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 3)'
.venv/bin/python -m pip install --disable-pip-version-check --requirement requirements.txt
exec .venv/bin/python scripts/harness.py verify harness
