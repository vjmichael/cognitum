#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
python3 scripts/prepare_baseline.py
if [[ "${EUID}" -ne 0 ]]; then
  echo "Live five-UID acceptance needs Linux root for disposable numeric UID isolation."
  exit 2
fi
python3 source/harness40g.py --mode "${1:-valid}"
