#!/usr/bin/env bash
set -e
python -m uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
npm --prefix src/frontend run dev -- --host 0.0.0.0
