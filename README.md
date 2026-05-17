# UninstallHub

UninstallHub is a GTK4/Libadwaita (Wayland-native) app for uninstalling software from many Linux sources in one place.

## Supported sources

- APT / dpkg
- Flatpak
- Snap
- AppImage
- pipx
- npm (global)
- cargo install
- Homebrew (Linuxbrew)
- Manual local `.desktop` entries

## New in v0.2

- Source filter chips: choose which sources to show and hide the rest.
- Animated uninstall progress bar while uninstall commands run.
- Expanded backend coverage (pipx, npm, cargo, brew, manual desktop launchers).
- Real app icon resolution from desktop launchers plus symbolic icon variant for dark/light themes.
- Debian package builder script for a proper `.deb` installer.

## Run

```bash
./run.sh
```

## Local install

```bash
./install.sh
```

## Build .deb installer

```bash
./packaging/build-deb.sh 0.2.0
```

The package will be created in `dist/` and can be installed with `sudo apt install ./dist/uninstallhub_0.2.0_all.deb`.
