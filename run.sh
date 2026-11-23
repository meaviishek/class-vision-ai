#!/usr/bin/env bash
# Starts ClassVision. Runs the one-time setup first if it has not been done yet.
cd "$(dirname "$0")" || exit 1
if [ ! -f .venv/.setup_done ]; then
  bash ./setup.sh || exit 1
fi
exec .venv/bin/python main.py
