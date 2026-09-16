#!/bin/sh
set -eu
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.10+ is required for the harness.' >&2; exit 3; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 3)'
exec python3 scripts/harness.py verify harness
