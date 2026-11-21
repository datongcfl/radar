#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
STAMP="${STAMP:-$(date +%Y%m%d-%H%M%S)}"
BASE_ROOT="${BASE_ROOT:-runs}"
PACK_ROOT="${PACK_ROOT:-packs}"
SEED_ROOT="${SEED_ROOT:-seeds}"
CODE=0
STATUSES=()
for name in weak-current video-kb data-center-ops pet-hospital; do
  pack="${PACK_ROOT}/${name}/pack.json"
  seeds="${SEED_ROOT}/${name}.json"
  [ -f "$pack" ] || continue
  last_file="${BASE_ROOT}/${name}-last.txt"
  last=""
  if [ -f "$last_file" ]; then last="$(cat "$last_file" 2>/dev/null || true)"; fi
  if [ -n "$last" ] && [ -d "$last" ]; then
    base="$last"
  else
    base="${BASE_ROOT}/${name}-demo"
  fi
  out="${BASE_ROOT}/${name}-scan-${STAMP}"
  echo "== $name -> $out (base $base)"
  set +e
  python3 -m radar scan --pack "$pack" --seeds "$seeds" \
    --title "$name scan" --out "$out" --base "$base" \
    --verify-quotes --require-web-verify --fail-on-change
  rc=$?
  set -e
  if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ]; then
    printf '%s\n' "$out" > "$last_file"
  fi
  if [ "$rc" -eq 1 ]; then
    CODE=1
  elif [ "$rc" -eq 2 ] && [ "$CODE" -ne 1 ]; then
    CODE=2
  fi
  STATUSES+=("$name=$rc")
done
echo "== status: ${STATUSES[*]}"
exit "$CODE"
