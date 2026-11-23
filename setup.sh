#!/usr/bin/env bash
# One-time setup: virtual environment, requirements, face models, then a first-run check.
set -e
cd "$(dirname "$0")"

PY=""
for candidate in "${PYTHON:-}" python3.13 python3.12 python3.11 python3.10 python3 python; do
  [ -n "$candidate" ] || continue
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)' 2>/dev/null; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 to 3.13 was not found. Install Python 3.12 (python.org or your package manager) and run this again."
  exit 1
fi
echo "Using: $PY ($("$PY" --version 2>&1))"

if [ ! -x .venv/bin/python ]; then
  echo "Creating a virtual environment in .venv ..."
  "$PY" -m venv .venv || {
    echo "Could not create the virtual environment. On Debian or Ubuntu run: sudo apt install python3-venv"
    exit 1
  }
fi

echo
echo "Installing requirements (the first time takes a few minutes) ..."
.venv/bin/python -m pip install --upgrade pip || true
.venv/bin/python -m pip install -r requirements.txt || {
  echo
  echo "Installing the requirements failed. Check your internet connection and run setup.sh again."
  exit 1
}
touch .venv/.setup_done

echo
echo "Fetching the face models ..."
.venv/bin/python scripts/download_models.py ||
  echo "The download failed. The app will offer to retry, or copy the two .onnx files into models/ (see README)."

echo
echo "Running the first-run check ..."
.venv/bin/python scripts/doctor.py || true

echo
echo "Setup finished. Start the app with:  bash run.sh"
