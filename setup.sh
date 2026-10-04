#!/usr/bin/env bash
# One-time environment setup: creates .venv, installs requirements, seeds config.yaml.
# After this, plain `make`, `make setup`, `make prune` and `app.py` all use the venv.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

command -v "$PYTHON" >/dev/null || { echo "error: '$PYTHON' not found on PATH" >&2; exit 1; }

if ! "$PYTHON" -m venv .venv 2>/dev/null; then
  echo "error: could not create venv — on Debian/Ubuntu run: sudo apt-get install python3-venv" >&2
  exit 1
fi

./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

if [ ! -f config.yaml ]; then
  cp config.yaml.example config.yaml
  echo "Created config.yaml from config.yaml.example — edit it before running a build."
fi

echo
echo "Environment ready."
echo "  Activate:  source .venv/bin/activate   (then 'python app.py', 'make', etc.)"
echo "  Or direct: .venv/bin/python app.py"
