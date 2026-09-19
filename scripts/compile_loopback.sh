#!/usr/bin/env bash
# Nuitka standalone of the loopback entry. Target scipy.ndimage — do not
# --include-package=scipy (that pulled the test suite: 45.8 min / 291 MB).
#
# Use the APP interpreter (FastAPI, uvicorn, pymongo installed), not the
# isolated spike venv. A compile that cannot `import fastapi` produces a
# binary that dies on boot.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${GOB_NUITKA_OUT:-dist/loopback}"
PYTHON="${GOB_NUITKA_PYTHON:-python3}"

"$PYTHON" - <<'PY'
import fastapi, pymongo, scipy.ndimage, uvicorn  # noqa: F401
print("compile-deps-ok", flush=True)
PY

exec "$PYTHON" -m nuitka \
  --standalone \
  --output-dir="$OUT" \
  --output-filename=gob-loopback \
  --include-package=BackEnd \
  --nofollow-import-to=BackEnd.tests \
  --include-package=fastapi \
  --include-package=starlette \
  --include-package=uvicorn \
  --include-package=pymongo \
  --include-module=scipy.ndimage \
  --nofollow-import-to=scipy.stats \
  --nofollow-import-to=scipy.io \
  --nofollow-import-to=scipy.optimize \
  --nofollow-import-to=scipy.integrate \
  --nofollow-import-to=scipy.signal \
  --include-data-dir=BackEnd/assets=BackEnd/assets \
  --include-data-dir=BackEnd/data=BackEnd/data \
  --include-data-dir=FrontEnd/static=FrontEnd/static \
  --include-data-dir=teams=teams \
  BackEnd/loopback.py
