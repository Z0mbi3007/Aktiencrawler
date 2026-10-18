#!/bin/bash
# =======================================================
# Start-Skript für den Wikifolio Depot-Tracker
# =======================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Virtuelle Umgebung nicht gefunden. Erstelle venv..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

exec ./venv/bin/python tracker.py "$@"
