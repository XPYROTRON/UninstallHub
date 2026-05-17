#!/usr/bin/env bash
set -euo pipefail
rm -rf "$HOME/.local/share/uninstallhub"
rm -f "$HOME/.local/share/applications/io.github.uninstallhub.UninstallHub.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.uninstallhub.UninstallHub.svg"
echo "UninstallHub local launcher removed."
