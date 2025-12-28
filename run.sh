#!/bin/bash
set -e

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate

pip install -r requirements.txt
playwright install chromium

uvicorn main:app --host 0.0.0.0 --port 8000