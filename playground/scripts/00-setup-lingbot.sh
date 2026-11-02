#!/usr/bin/env bash
# Install LingBot-Map (MLX port, Apple Silicon) into playground/vendor/.
#
# Clones the port at a pinned commit and creates a Python 3.10 venv next to it.
# The FP16 weights (2.2 GB) are fetched from Hugging Face by create_map.py on its
# first run, so this script stays quick.
#
# Usage: ./00-setup-lingbot.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor"
REPO="https://github.com/uqer1244/mlx_lingbot-map.git"
COMMIT="a2fe95c9c83ef5e88d4de83cc51404c0eee19dfb"
PYTHON="${PYTHON:-python3.10}"

[ "$(uname -sm)" = "Darwin arm64" ] || { echo "MLX needs an Apple Silicon Mac." >&2; exit 1; }
command -v "$PYTHON" >/dev/null || { echo "$PYTHON not found (set PYTHON=...)." >&2; exit 1; }

mkdir -p "$VENDOR"
if [ ! -d "$VENDOR/mlx_lingbot-map/.git" ]; then
  git clone "$REPO" "$VENDOR/mlx_lingbot-map"
fi
git -C "$VENDOR/mlx_lingbot-map" checkout --quiet "$COMMIT"

if [ ! -x "$VENDOR/.venv-lingbot/bin/python" ]; then
  "$PYTHON" -m venv "$VENDOR/.venv-lingbot"
fi
# opencv, scipy and trimesh come with the port; export-web.py relies on them.
"$VENDOR/.venv-lingbot/bin/pip" install --quiet -e "$VENDOR/mlx_lingbot-map" huggingface_hub

echo "LingBot-Map ready: $VENDOR/mlx_lingbot-map"
