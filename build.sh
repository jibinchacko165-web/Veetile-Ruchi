#!/usr/bin/env bash
# Zoho Catalyst / Linux Production Build Script
set -e

echo "=== [1/3] Installing Python Dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [2/3] Collecting Static Files with WhiteNoise ==="
python manage.py collectstatic --noinput --clear

echo "=== [3/3] Applying Database Migrations ==="
python manage.py migrate --noinput

echo "=== Production Build Completed Successfully! ==="
