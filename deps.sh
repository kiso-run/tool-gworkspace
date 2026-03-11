#!/usr/bin/env bash
# Install the Google Workspace CLI (gws).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Install Python dev dependencies
uv sync

# Install gws CLI
npm install -g @googleworkspace/cli
