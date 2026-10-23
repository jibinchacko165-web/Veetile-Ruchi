#!/bin/sh
echo "=== Starting Veetile-Ruchi via run.sh ==="
echo "PORT: $X_ZOHO_CATALYST_LISTEN_PORT"

if command -v python3 >/dev/null 2>&1; then
    exec python3 app.py
elif command -v python >/dev/null 2>&1; then
    exec python app.py
else
    echo "FATAL: Neither python3 nor python found in PATH!"
    exit 1
fi
