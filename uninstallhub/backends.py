from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import shutil
import subprocess
from typing import Iterable


SOURCE_LABELS = {
    "apt": "APT / dpkg",
    "flatpak": "Flatpak",
    "snap": "Snap",
    "appimage": "AppImage",
    "pipx": "pipx",
    "npm": "npm (global)",
    "cargo": "cargo install",
    "homebrew": "Homebrew (Linuxbrew)",
    "manual": "Manual local .desktop entries",
}


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
    candidates = [f"{app_id}.desktop"] if app_id else []
    if source == "Snap":
        candidates.append(f"{app_id}_{app_id}.desktop")

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

    for path in files:
        visible_name = _read_desktop_value(path, "Name")
        exec_line = _read_desktop_value(path, "Exec")
        search = _normalize(f"{visible_name} {exec_line} {path.stem}")
        if (norm_app and norm_app in search) or (norm_name and norm_name in search):
            return path
    return None


def _icon_from_desktop(path: Path | None) -> str:
    if not path:
        return ""
    return _read_desktop_value(path, "Icon") or ""


def resolve_icon(app_id: str, name: str, source: str, path: str = "") -> str:
    if source in set(SOURCE_LABELS.values()) | {"deb"}:
        icon = _icon_from_desktop(_find_desktop_for_app(app_id, name, source))
        if icon:
            return icon
    if source == "AppImage" and path:
        p = Path(path)
        for suffix in (".png", ".svg", ".xpm"):
            candidate = p.with_suffix(suffix)
            if candidate.exists():
                return str(candidate)
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
        pkg, version, status = parts
        if not status.startswith("ii"):
            continue
        if pkg.startswith(("lib", "gir1.2-", "python3-", "linux-", "fonts-")):
            continue
        source = SOURCE_LABELS["apt"]
        icon = resolve_icon(pkg, pkg, source)
        apps.append(InstalledApp(name=pkg, app_id=pkg, source=source, version=version, detail="Debian/Ubuntu package", icon=icon))
    return apps


def scan_flatpak() -> list[InstalledApp]:
    if not command_exists("flatpak"):
        return []
    apps: list[InstalledApp] = []
    for line in run_lines(["flatpak", "list", "--app", "--columns=name,application,version"]):
        parts = line.split("\t")
        if len(parts) >= 2:
            name, app_id = parts[0], parts[1]
            version = parts[2] if len(parts) > 2 else ""
            source = SOURCE_LABELS["flatpak"]
            apps.append(InstalledApp(name=name, app_id=app_id, source=source, version=version, detail=app_id, icon=resolve_icon(app_id, name, source)))
    return apps


def scan_snap() -> list[InstalledApp]:
    if not command_exists("snap"):
        return []
    apps: list[InstalledApp] = []
    for line in run_lines(["snap", "list"])[1:]:
        parts = line.split()
        if len(parts) >= 2:
            name, version = parts[0], parts[1]
            source = SOURCE_LABELS["snap"]
            apps.append(InstalledApp(name=name, app_id=name, source=source, version=version, detail="Snap package", icon=resolve_icon(name, name, source)))
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
            source = SOURCE_LABELS["appimage"]
            apps.append(InstalledApp(name=path.stem, app_id=path.name, source=source, detail=str(path), path=str(path), icon=resolve_icon(path.name, path.stem, source, str(path))))
    return apps


def _scan_json_apps(cmd: list[str], source: str, key_name: str = "name", key_version: str = "version") -> list[InstalledApp]:
    text = run_text(cmd)
    if not text:
        return []
    try:
        obj = json.loads(text)
    except Exception:
        return []
    items = obj if isinstance(obj, list) else obj.values() if isinstance(obj, dict) else []
    apps = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get(key_name, "")).strip()
        if not name:
            continue
        version = str(item.get(key_version, "")).strip()
        icon = resolve_icon(name, name, source)
        apps.append(InstalledApp(name=name, app_id=name, source=source, version=version, detail=f"{source} package", icon=icon))
    return apps


def scan_pipx() -> list[InstalledApp]:
    if not command_exists("pipx"):
        return []
    return _scan_json_apps(["pipx", "list", "--json"], SOURCE_LABELS["pipx"], key_name="package", key_version="package_version")


def scan_npm_global() -> list[InstalledApp]:
    if not command_exists("npm"):
        return []
    return _scan_json_apps(["npm", "ls", "-g", "--json", "--depth=0"], SOURCE_LABELS["npm"], key_name="name", key_version="version")


def scan_cargo() -> list[InstalledApp]:
    if not command_exists("cargo"):
        return []
    apps: list[InstalledApp] = []
    for line in run_lines(["cargo", "install", "--list"]):
        if not line or line.startswith(" ") or not line.endswith(":"):
            continue
        name_version = line[:-1]
        if " v" in name_version:
            name, version = name_version.rsplit(" v", 1)
        else:
            name, version = name_version, ""
        source = SOURCE_LABELS["cargo"]
        icon = resolve_icon(name, name, source)
        apps.append(InstalledApp(name=name, app_id=name, source=source, version=version, detail="Cargo install", icon=icon))
    return apps


def scan_homebrew() -> list[InstalledApp]:
    if not command_exists("brew"):
        return []
    text = run_text(["brew", "list", "--formula", "--versions"])
    apps: list[InstalledApp] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        name, versions = parts[0], " ".join(parts[1:])
        source = SOURCE_LABELS["homebrew"]
        icon = resolve_icon(name, name, source)
        apps.append(InstalledApp(name=name, app_id=name, source=source, version=versions, detail="Homebrew formula", icon=icon))
    return apps


def scan_manual_desktop() -> list[InstalledApp]:
    apps: list[InstalledApp] = []
    for path in (Path.home() / ".local/share/applications").glob("*.desktop"):
        if "flatpak" in str(path) or "snap" in str(path):
            continue
        name = _read_desktop_value(path, "Name") or path.stem
        icon = _read_desktop_value(path, "Icon")
        exec_line = _read_desktop_value(path, "Exec")
        apps.append(InstalledApp(name=name, app_id=path.name, source=SOURCE_LABELS["manual"], detail=exec_line or str(path), path=str(path), icon=icon))
    return apps


def scan_all() -> list[InstalledApp]:
    apps: list[InstalledApp] = []
    scanners: Iterable = [scan_flatpak, scan_snap, scan_appimages, scan_apt, scan_pipx, scan_npm_global, scan_cargo, scan_homebrew, scan_manual_desktop]
    for scanner in scanners:
        apps.extend(scanner())
    return sorted(apps, key=lambda a: (a.source.lower(), a.name.lower()))


def uninstall_command(app: InstalledApp) -> list[str]:
    if app.source == SOURCE_LABELS["apt"]:
        return ["pkexec", "apt", "remove", app.app_id]
    if app.source == SOURCE_LABELS["flatpak"]:
        return ["flatpak", "uninstall", app.app_id]
    if app.source == SOURCE_LABELS["snap"]:
        return ["pkexec", "snap", "remove", app.app_id]
    if app.source == SOURCE_LABELS["appimage"]:
        return ["rm", "--", app.path]
    if app.source == SOURCE_LABELS["pipx"]:
        return ["pipx", "uninstall", app.app_id]
    if app.source == SOURCE_LABELS["npm"]:
        return ["npm", "uninstall", "-g", app.app_id]
    if app.source == SOURCE_LABELS["cargo"]:
        return ["cargo", "uninstall", app.app_id]
    if app.source == SOURCE_LABELS["homebrew"]:
        return ["brew", "uninstall", app.app_id]
    if app.source == SOURCE_LABELS["manual"]:
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
