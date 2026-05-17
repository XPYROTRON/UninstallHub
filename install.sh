#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/uninstallhub"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR" "$ICON_DIR"
rsync -a --delete --exclude='.git' "$APP_DIR/" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/run.sh"
cp "$INSTALL_DIR/assets/io.github.uninstallhub.UninstallHub.svg" "$ICON_DIR/io.github.uninstallhub.UninstallHub.svg"
cp "$INSTALL_DIR/assets/io.github.uninstallhub.UninstallHub-symbolic.svg" "$ICON_DIR/io.github.uninstallhub.UninstallHub-symbolic.svg"
sed "s|UNINSTALLHUB_EXEC|$INSTALL_DIR/run.sh|" \
  "$INSTALL_DIR/share/applications/io.github.uninstallhub.UninstallHub.desktop" \
  > "$DESKTOP_DIR/io.github.uninstallhub.UninstallHub.desktop"
chmod +x "$DESKTOP_DIR/io.github.uninstallhub.UninstallHub.desktop"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" || true
fi

echo "UninstallHub installed. Launch it from your app menu, or run: $INSTALL_DIR/run.sh"
