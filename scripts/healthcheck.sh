#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://localhost:8000}"
python -c "import os, urllib.request; base=os.environ['BASE_URL']; urllib.request.urlopen(base + '/api/health'); urllib.request.urlopen(base + '/api/readiness')"
