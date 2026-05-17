from __future__ import annotations

import threading
from pathlib import Path
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from .backends import SOURCE_LABELS, InstalledApp, scan_all, uninstall_app, uninstall_command


class AppRow(Gtk.ListBoxRow):
    def __init__(self, app: InstalledApp):
        super().__init__()
        self.app = app
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon = self._build_icon(app)
        icon.set_pixel_size(40)
        icon.set_margin_top(2)
        icon.set_margin_bottom(2)
        box.append(icon)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        title = Gtk.Label(label=app.name, xalign=0)
        title.add_css_class("heading")
        title.set_ellipsize(3)
        subtitle_text = f"{app.source}"
        if app.version:
            subtitle_text += f" · {app.version}"
        if app.detail:
            subtitle_text += f" · {app.detail}"
        subtitle = Gtk.Label(label=subtitle_text, xalign=0)
        subtitle.add_css_class("dim-label")
        subtitle.set_ellipsize(3)
        text.append(title)
        text.append(subtitle)
        box.append(text)
        self.set_child(box)

    @staticmethod
    def _build_icon(app: InstalledApp) -> Gtk.Image:
        icon_value = getattr(app, "icon", "") or ""
        if icon_value:
            icon_path = Path(icon_value).expanduser()
            if icon_path.is_file():
                try:
                    return Gtk.Image.new_from_file(str(icon_path))
                except Exception:
                    pass
            return Gtk.Image.new_from_icon_name(icon_value)
        return Gtk.Image.new_from_icon_name(AppRow._fallback_icon_name(app.source))

    @staticmethod
    def _fallback_icon_name(source: str) -> str:
        return {
            SOURCE_LABELS["apt"]: "application-x-executable",
            SOURCE_LABELS["flatpak"]: "package-x-generic",
            SOURCE_LABELS["snap"]: "package-x-generic",
            SOURCE_LABELS["appimage"]: "application-x-executable",
        }.get(source, "application-x-executable")


class UninstallHubWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title("UninstallHub")
        self.set_default_size(900, 650)
        self.apps: list[InstalledApp] = []

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        self.refresh_button.connect("clicked", lambda *_: self.refresh())
        header.pack_end(self.refresh_button)
        toolbar.add_top_bar(header)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main.set_margin_top(12)
        main.set_margin_bottom(12)
        main.set_margin_start(12)
        main.set_margin_end(12)
        toolbar.set_content(main)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search installed apps")
        self.search.connect("search-changed", lambda *_: self.populate())
        main.append(self.search)

        self.visible_sources: set[str] = set()
        self.filter_expander = Gtk.Expander(label="Filter repositories")
        self.filter_expander.set_expanded(False)
        self.filter_flow = Gtk.FlowBox()
        self.filter_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.filter_flow.set_row_spacing(6)
        self.filter_flow.set_column_spacing(6)
        self.filter_expander.set_child(self.filter_flow)
        main.append(self.filter_expander)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("Ready")
        self.progress.set_visible(False)
        main.append(self.progress)

        self.status = Gtk.Label(label="Scanning…", xalign=0)
        self.status.add_css_class("dim-label")
        main.append(self.status)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.add_css_class("boxed-list")
        self.listbox.connect("row-activated", self.on_row_activated)
        scrolled.set_child(self.listbox)
        main.append(scrolled)

        self.refresh()

    def toast(self, message: str):
        self.toast_overlay.add_toast(Adw.Toast(title=message))

    def refresh(self):
        self.refresh_button.set_sensitive(False)
        self.status.set_label("Scanning installed apps…")
        self.clear_list()

        def worker():
            apps = scan_all()
            GLib.idle_add(self.finish_refresh, apps)

        threading.Thread(target=worker, daemon=True).start()

    def finish_refresh(self, apps: list[InstalledApp]):
        self.apps = apps
        self.refresh_button.set_sensitive(True)
        self.populate()
        self.update_source_filters()
        self.status.set_label(f"Found {len(apps)} removable items.")
        return False

    def clear_list(self):
        child = self.listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.listbox.remove(child)
            child = next_child

    def update_source_filters(self):
        child = self.filter_flow.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.filter_flow.remove(child)
            child = nxt
        discovered = {a.source for a in self.apps}
        sources = [
            SOURCE_LABELS["apt"],
            SOURCE_LABELS["flatpak"],
            SOURCE_LABELS["snap"],
            SOURCE_LABELS["appimage"],
            SOURCE_LABELS["pipx"],
            SOURCE_LABELS["npm"],
            SOURCE_LABELS["cargo"],
            SOURCE_LABELS["homebrew"],
            SOURCE_LABELS["manual"],
        ]
        if not self.visible_sources:
            self.visible_sources = set(sources)
        else:
            self.visible_sources &= set(sources)
        for source in sources:
            chip = Gtk.CheckButton(label=source)
            chip.set_active(source in self.visible_sources)
            chip.set_sensitive(source in discovered)
            if source not in discovered:
                chip.set_tooltip_text("No installed apps found for this source")
            chip.connect("toggled", self.on_source_toggled, source)
            self.filter_flow.insert(chip, -1)

    def on_source_toggled(self, button: Gtk.CheckButton, source: str):
        if button.get_active():
            self.visible_sources.add(source)
        else:
            self.visible_sources.discard(source)
        self.populate()

    def populate(self):
        query = self.search.get_text().strip().lower()
        self.clear_list()
        for app in self.apps:
            if self.visible_sources and app.source not in self.visible_sources:
                continue
            haystack = f"{app.name} {app.app_id} {app.source} {app.detail}".lower()
            if query and query not in haystack:
                continue
            self.listbox.append(AppRow(app))


    def on_row_activated(self, _box, row: AppRow):
        app = row.app
        cmd = " ".join(uninstall_command(app))
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Uninstall {app.name}?",
            body=f"Source: {app.source}\n\nCommand:\n{cmd}",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("uninstall", "Uninstall")
        dialog.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self.confirm_uninstall, app)
        dialog.present()

    def confirm_uninstall(self, dialog, response: str, app: InstalledApp):
        if response != "uninstall":
            return
        self.status.set_label(f"Uninstalling {app.name}…")
        self.refresh_button.set_sensitive(False)
        self.progress.set_visible(True)
        self.progress.set_fraction(0.1)
        self.progress.set_text(f"Uninstalling {app.name}")
        pulse_id = GLib.timeout_add(120, self.progress.pulse)

        def worker():
            ok, output = uninstall_app(app)
            GLib.idle_add(self.finish_uninstall, ok, output, pulse_id)

        threading.Thread(target=worker, daemon=True).start()

    def finish_uninstall(self, ok: bool, output: str, pulse_id: int):
        GLib.source_remove(pulse_id)
        self.refresh_button.set_sensitive(True)
        self.progress.set_fraction(1.0 if ok else 0.0)
        self.progress.set_text("Done" if ok else "Failed")
        self.toast("Uninstalled successfully" if ok else "Uninstall failed")
        self.status.set_label(output[:500])
        self.refresh()
        return False


class UninstallHubApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.uninstallhub.UninstallHub")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = UninstallHubWindow(self)
        win.present()


def main():
    Adw.init()
    app = UninstallHubApp()
    raise SystemExit(app.run(None))
