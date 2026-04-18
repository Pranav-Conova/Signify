#!/usr/bin/env bash
# Render build script
set -o errexit

pip install -r requirements.txt

# Install LibreOffice for PPTX conversion
apt-get update && apt-get install -y --no-install-recommends libreoffice

python manage.py collectstatic --noinput
python manage.py migrate
