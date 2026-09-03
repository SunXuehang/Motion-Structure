#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
freecad_app="${FREECAD_APPIMAGE:-/home/sunxuehang/Applications/FreeCAD_1.1.3-Linux-x86_64-py311.AppImage}"
export PYTHONPATH="$project_root/src${PYTHONPATH:+:$PYTHONPATH}"
export QT_QPA_PLATFORM=offscreen
cd "$project_root"
exec "$freecad_app" --console -P "$project_root/src" \
  "$project_root/scripts/freecad_python.py" --pass "$@"
