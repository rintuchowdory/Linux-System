#!/usr/bin/env python3
import gi
import psutil
import subprocess
import os

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk

class SystemPanel(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Linux-System")
        self.set_default_size(1000, 70)
        self.set_resizable(False)

        # Main horizontal box
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_margin_start(15)
        main_box.set_margin_end(15)
        self.set_child(main_box)

        # === LEFT: Quick Launch Icons ===
        icons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.append(icons_box)

        for name, icon_name, cmd in [
            ("Home", "user-home", "nautilus"),
            ("Settings", "preferences-system", "gnome-control-center"),
            ("Trash", "user-trash", "nautilus trash:///"),
            ("Browser", "web-browser", "firefox"),
            ("Editor", "text-editor", "gedit"),
            ("Calendar", "x-office-calendar", "gnome-calendar"),
            ("Terminal", "utilities-terminal", "gnome-terminal"),
        ]:
            btn = self._create_icon_button(name, icon_name, cmd)
            icons_box.append(btn)

        # === CENTER: System Stats ===
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        stats_box.set_hexpand(True)
        stats_box.set_halign(Gtk.Align.CENTER)
        main_box.append(stats_box)

        self.cpu_label = Gtk.Label(label="CPU: --%")
        self.ram_label = Gtk.Label(label="RAM: --%")
        self.net_label = Gtk.Label(label="↓-- ↑--")
        self.disk_label = Gtk.Label(label="Disk: --%")

        for lbl in (self.cpu_label, self.ram_label, self.net_label, self.disk_label):
            lbl.add_css_class("monospace")
            stats_box.append(lbl)

        # === RIGHT: Action Buttons ===
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        main_box.append(actions_box)

        self.replay_btn = Gtk.Button(label="Replay")
        self.replay_btn.connect("clicked", self.on_replay)
        actions_box.append(self.replay_btn)

        self.remix_btn = Gtk.Button(label="Remix")
        self.remix_btn.add_css_class("suggested-action")
        self.remix_btn.connect("clicked", self.on_remix)
        actions_box.append(self.remix_btn)

        # Start update loop
        self.last_net = psutil.net_io_counters()
        GLib.timeout_add_seconds(1, self.update_stats)
        self.update_stats()

    def _create_icon_button(self, tooltip, icon_name, cmd):
        btn = Gtk.Button()
        btn.set_tooltip_text(tooltip)
        btn.set_has_frame(False)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(24)
        btn.set_child(icon)
        btn.connect("clicked", lambda *_: subprocess.Popen(cmd, shell=True))
        return btn

    def update_stats(self):
        # CPU
        cpu = psutil.cpu_percent()
        self.cpu_label.set_text(f"CPU: {cpu:.0f}%")

        # RAM
        ram = psutil.virtual_memory()
        self.ram_label.set_text(f"RAM: {ram.percent:.0f}%")

        # Network
        net = psutil.net_io_counters()
        down = (net.bytes_recv - self.last_net.bytes_recv) / 1024
        up = (net.bytes_sent - self.last_net.bytes_sent) / 1024
        self.net_label.set_text(f"↓{down:.0f} ↑{up:.0f} KB/s")
        self.last_net = net

        # Disk
        disk = psutil.disk_usage('/')
        self.disk_label.set_text(f"Disk: {disk.percent:.0f}%")

        return True

    def on_replay(self, btn):
        # Placeholder: run last command or macro
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Replay Action",
        )
        dialog.set_secondary_text("Replay last system action or macro.")
        dialog.connect("response", lambda d, _: d.destroy())
        dialog.present()

    def on_remix(self, btn):
        # Placeholder: theme/workspace switcher
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Remix Mode",
        )
        dialog.set_secondary_text("Switch themes or workspace layout.")
        dialog.connect("response", lambda d, _: d.destroy())
        dialog.present()

def on_activate(app):
    win = SystemPanel(app)
    win.present()

app = Gtk.Application(application_id="com.rintuchowdory.linux-system")
app.connect("activate", on_activate)
app.run(None)
