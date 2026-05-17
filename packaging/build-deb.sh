#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-0.2.0}"
PKGDIR="$ROOT/dist/uninstallhub_${VERSION}_all"
rm -rf "$PKGDIR"
mkdir -p "$PKGDIR/DEBIAN" "$PKGDIR/usr/share/uninstallhub" "$PKGDIR/usr/share/applications" "$PKGDIR/usr/share/icons/hicolor/scalable/apps"
cp -a "$ROOT/uninstallhub" "$ROOT/run.sh" "$ROOT/requirements.txt" "$PKGDIR/usr/share/uninstallhub/"
cp "$ROOT/share/applications/io.github.uninstallhub.UninstallHub.desktop" "$PKGDIR/usr/share/applications/"
sed -i 's|UNINSTALLHUB_EXEC|/usr/share/uninstallhub/run.sh|' "$PKGDIR/usr/share/applications/io.github.uninstallhub.UninstallHub.desktop"
cp "$ROOT/assets/io.github.uninstallhub.UninstallHub.svg" "$PKGDIR/usr/share/icons/hicolor/scalable/apps/"
cp "$ROOT/assets/io.github.uninstallhub.UninstallHub-symbolic.svg" "$PKGDIR/usr/share/icons/hicolor/scalable/apps/"
cat > "$PKGDIR/DEBIAN/control" <<EOF
Package: uninstallhub
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Maintainer: UninstallHub
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1
Description: Unified Linux app uninstaller for multiple package sources
EOF
dpkg-deb --build "$PKGDIR"
echo "Built: $PKGDIR.deb"
