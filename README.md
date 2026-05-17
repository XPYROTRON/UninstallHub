# UninstallHub

A simple Adwaita GTK app for Ubuntu/Linux that lists apps installed from APT, Flatpak, Snap, and AppImage files, shows application icons where available, then uninstalls them through the correct backend.

## Install dependencies on Ubuntu

```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 policykit-1 rsync desktop-file-utils
```

Optional backends:

```bash
sudo apt install flatpak snapd
```

## Run without installing

```bash
cd UninstallHub
./run.sh
```

## Install as a local desktop app

```bash
cd UninstallHub
./install.sh
```

Then open **UninstallHub** from the Ubuntu app menu.

To remove the local desktop launcher:

```bash
~/.local/share/uninstallhub/uninstall-local.sh
```

## Icon support

UninstallHub now tries to resolve real application icons from `.desktop` launchers in:

- `~/.local/share/applications`
- `/usr/share/applications`
- `/usr/local/share/applications`
- `/var/lib/flatpak/exports/share/applications`
- `~/.local/share/flatpak/exports/share/applications`
- `/var/lib/snapd/desktop/applications`

If no matching icon is found, it falls back to a generic package/application icon.

## Safety model

UninstallHub does not blindly delete random files. It detects the source first and then runs the proper uninstall command:

- APT: `pkexec apt remove <package>`
- Flatpak: `flatpak uninstall <app_id>`
- Snap: `pkexec snap remove <snap>`
- AppImage: remove the selected AppImage file after confirmation

AppImage detection scans:

- `~/Applications`
- `~/.local/bin`
- `~/Downloads`
  
=======

UninstallHub is a native GTK4/Adwaita Linux app that makes uninstalling APT, Flatpak, Snap, and AppImage apps easier from one clean interface.
