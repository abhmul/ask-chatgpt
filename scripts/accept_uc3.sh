#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="tmp/accept-uc3-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
echo "artifact_dir=$OUT"

set +e
uv run python scripts/accept_uc3.py --out "$OUT" 2>&1 | tee "$OUT/stdout.log"
status=${PIPESTATUS[0]}
set -e

echo "artifact_dir=$OUT"
exit "$status"
