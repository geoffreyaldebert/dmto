#!/usr/bin/env bash
# Lance le nowcasting DMTO (OpenMP requis pour LightGBM / XGBoost sur macOS).
set -euo pipefail
cd "$(dirname "$0")"
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:${DYLD_LIBRARY_PATH:-}"
python3 run_nowcast.py "$@"
