from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
from typing import Dict


@dataclass(frozen=True)
class InstalledApp:
    name: str
    app_id: str
    source: str
    version: str = ""
    detail: str = ""
    path: str = ""
    icon: str = ""


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run_lines(cmd: list[str]) -> list[str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def run_text(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    except Exception:
        return ""


def _desktop_dirs() -> list[Path]:
    return [
        Path.home() / ".local/share/applications",
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local/share/flatpak/exports/share/applications",
        Path("/var/lib/snapd/desktop/applications"),
    ]


def _read_desktop_value(path: Path, key: str) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _desktop_files() -> list[Path]:
    files: list[Path] = []
    for directory in _desktop_dirs():
        if directory.exists():
            files.extend(directory.glob("*.desktop"))
    return files


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _find_desktop_for_app(app_id: str, name: str, source: str) -> Path | None:
    files = _desktop_files()

    # Exact package/app-id style matches first.
    candidates = []
    if source == "Flatpak":
        candidates = [f"{app_id}.desktop"]
    elif source == "Snap":
        candidates = [f"{app_id}.desktop", f"{app_id}_{app_id}.desktop"]
    else:
        candidates = [f"{app_id}.desktop"]
    for candidate in candidates:
        for path in files:
            if path.name == candidate:
                return path

    norm_app = _normalize(app_id)
    norm_name = _normalize(name)
    for path in files:
        stem = _normalize(path.stem)
        if stem and (stem == norm_app or stem == norm_name):
            return path

    # Fuzzy match visible name and executable command. Kept conservative.
    for path in files:
        visible_name = _read_desktop_value(path, "Name")
        exec_line = _read_desktop_value(path, "Exec")
        search = _normalize(f"{visible_name} {exec_line} {path.stem}")
        if norm_app and norm_app in search:
            return path
        if norm_name and norm_name in search:
            return path
    return None


def _icon_from_desktop(path: Path | None) -> str:
    if not path:
        return ""
    icon = _read_desktop_value(path, "Icon")
    return icon or ""


def resolve_icon(app_id: str, name: str, source: str, path: str = "") -> str:
    if source == "Flatpak" and app_id:
        icon = _icon_from_desktop(_find_desktop_for_app(app_id, name, source))
        return icon or app_id
    if source == "Snap" and app_id:
        icon = _icon_from_desktop(_find_desktop_for_app(app_id, name, source))
        return icon or app_id
    if source == "APT":
        return _icon_from_desktop(_find_desktop_for_app(app_id, name, source))
    if source == "AppImage":
        desktop = _find_desktop_for_app(app_id, name, source)
        icon = _icon_from_desktop(desktop)
        if icon:
            return icon
        # Some AppImage launchers create adjacent icons; check common image names.
        p = Path(path) if path else None
        if p:
            for suffix in (".png", ".svg", ".xpm"):
                candidate = p.with_suffix(suffix)
                if candidate.exists():
                    return str(candidate)
        return "application-x-executable"
    return ""


def scan_apt() -> list[InstalledApp]:
    if not command_exists("dpkg-query"):
        return []
    lines = run_lines(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${db:Status-Abbrev}\n"])
    apps: list[InstalledApp] = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        pkg, version, status = parts[0], parts[1], parts[2]
        if not status.startswith("ii"):
            continue
        if pkg.startswith(("lib", "gir1.2-", "python3-", "linux-", "fonts-")):
            continue
        icon = resolve_icon(pkg, pkg, "APT")
        apps.append(InstalledApp(name=pkg, app_id=pkg, source="APT", version=version, detail="Debian/Ubuntu package", icon=icon))
    return apps


def scan_flatpak() -> list[InstalledApp]:
    if not command_exists("flatpak"):
        return []
    lines = run_lines(["flatpak", "list", "--app", "--columns=name,application,version"])
    apps: list[InstalledApp] = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) >= 2:
            name, app_id = parts[0], parts[1]
            version = parts[2] if len(parts) > 2 else ""
            icon = resolve_icon(app_id, name, "Flatpak")
            apps.append(InstalledApp(name=name, app_id=app_id, source="Flatpak", version=version, detail=app_id, icon=icon))
    return apps


def scan_snap() -> list[InstalledApp]:
    if not command_exists("snap"):
        return []
    lines = run_lines(["snap", "list"])
    apps: list[InstalledApp] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            name, version = parts[0], parts[1]
            icon = resolve_icon(name, name, "Snap")
            apps.append(InstalledApp(name=name, app_id=name, source="Snap", version=version, detail="Snap package", icon=icon))
    return apps


def scan_appimages() -> list[InstalledApp]:
    locations = [Path.home() / "Applications", Path.home() / ".local/bin", Path.home() / "Downloads"]
    apps: list[InstalledApp] = []
    seen: set[str] = set()
    for base in locations:
        if not base.exists():
            continue
        for path in base.rglob("*.AppImage"):
            real = str(path.resolve())
            if real in seen:
                continue
            seen.add(real)
            icon = resolve_icon(path.name, path.stem, "AppImage", str(path))
            apps.append(InstalledApp(name=path.stem, app_id=path.name, source="AppImage", detail=str(path), path=str(path), icon=icon))
    return apps


def scan_all() -> list[InstalledApp]:
    apps = []
    apps.extend(scan_flatpak())
    apps.extend(scan_snap())
    apps.extend(scan_appimages())
    apps.extend(scan_apt())
    return sorted(apps, key=lambda a: (a.source.lower(), a.name.lower()))


def uninstall_command(app: InstalledApp) -> list[str]:
    if app.source == "APT":
        return ["pkexec", "apt", "remove", app.app_id]
    if app.source == "Flatpak":
        return ["flatpak", "uninstall", app.app_id]
    if app.source == "Snap":
        return ["pkexec", "snap", "remove", app.app_id]
    if app.source == "AppImage":
        return ["rm", "--", app.path]
    raise ValueError(f"Unsupported source: {app.source}")


def uninstall_app(app: InstalledApp) -> tuple[bool, str]:
    cmd = uninstall_command(app)
    try:
        proc = subprocess.run(cmd, text=True, input="y\n", capture_output=True)
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode == 0, output or "Done."
    except Exception as exc:
        return False, str(exc)
