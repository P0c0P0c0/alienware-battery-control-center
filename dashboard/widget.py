#!/usr/bin/python3
import datetime
from pathlib import Path
import sys
sys.dont_write_bytecode = True

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from chart import (GAUGE_SIZE, HEIGHT, HISTORY_DIVISIONS, SCALE_HEIGHT, SCALE_WIDTH,
                   SYMBOL_SIZE, TIME_HEIGHT, WIDTH,
                   button_symbol, charge_target, gauge_reading, history_layout, paint_gauge,
                   paint_history, paint_history_time, paint_scale, raster)
from telemetry import PERIODS, BackendCache, freshness, live

APP_ID = "io.github.bat07.Widget"
ROOT = Path(__file__).resolve().parent
WINDOW_WIDTH = 384
PERIOD_LABELS = dict(zip(PERIODS, ("24H", "7D", "30D")))
TONES = ("good", "warning", "danger", "muted")


def formatted(value, pattern):
    return "—" if value is None else pattern.format(value)


def stamp(seconds):
    return datetime.datetime.fromtimestamp(seconds).strftime("%H:%M:%S")


def label(text="", *classes, xalign=0):
    field = Gtk.Label(label=text, xalign=xalign)
    for name in classes:
        field.get_style_context().add_class(name)
    return field


def panel():
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.get_style_context().add_class("panel")
    return box


def status_tone(backend, age):
    if backend.status == "GAGAL SAMPLING":
        return "danger"
    if age.startswith("STALE") or backend.timestamp is None:
        return "warning"
    return "good"


class Widget(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.labels = {}
        self.gauges = {}
        self.images = {}
        self.history_layouts = {}
        self.history_rasters = {}
        self.clock_values = None
        self.tones = {}
        self.backend_cache = BackendCache()
        self.backend = None
        self.backend_at = 0
        self.last_tick = 0
        self.selected_period = next(iter(PERIODS))

    def do_command_line(self, command):
        arguments = command.get_arguments()[1:]
        action = arguments[0] if arguments else "show"
        if len(arguments) > 1 or action not in ("show", "hide", "toggle", "quit"):
            return 2
        if action == "quit":
            self.quit()
        elif action == "hide" or (action == "toggle" and self.window and self.window.get_visible()):
            if self.window:
                self.window.hide()
        else:
            self.activate()
        return 0

    def do_activate(self):
        if self.window is None:
            self.create_window()
            self.refresh()
            self.timer = GLib.timeout_add(2000, self.refresh)
        self.window.show_all()
        self.window.present()

    def create_window(self):
        self.window = Gtk.ApplicationWindow(application=self, title="BAT-07 · Alienware")
        self.window.set_name("bat07-window")
        self.window.set_default_size(WINDOW_WIDTH, -1)
        self.window.set_decorated(False)
        self.window.set_keep_above(True)
        self.window.connect("delete-event", self.hide_window)
        display = self.window.get_display()
        if "X11" in display.__gtype__.name:
            self.window.connect("map", self.place_x11)

        css = Gtk.CssProvider()
        css.load_from_path(str(ROOT / "widget.css"))
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_name("surface")
        scroll = Gtk.ScrolledWindow()
        scroll.set_name("dashboard-scroll")
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor:
            workarea = monitor.get_workarea()
            if workarea.height > 32:
                scroll.set_max_content_height(workarea.height - 32)
        scroll.add(box)
        self.window.add(scroll)
        self.build_header(box)
        self.build_gauges(box)
        self.build_telemetry(box)
        self.build_protection(box)
        self.build_history(box)
        self.build_footer(box)

    def symbol_button(self, symbol, description, action=None):
        button = Gtk.Button() if action else Gtk.ToggleButton()
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(button_symbol(symbol)), GdkPixbuf.Colorspace.RGB, True, 8,
            SYMBOL_SIZE, SYMBOL_SIZE, 4 * SYMBOL_SIZE)
        button.add(Gtk.Image.new_from_pixbuf(pixbuf))
        button.set_tooltip_text(description)
        button.get_accessible().set_name(description)
        if action:
            button.connect("clicked", action)
        return button

    @staticmethod
    def toggle_settings(button, popover):
        if button.get_active():
            popover.popup()
        elif popover.get_visible():
            popover.popdown()

    def build_header(self, box):
        header = Gtk.Box(spacing=5)
        drag = Gtk.EventBox()
        drag.add(label("ALIENWARE", "brand"))
        drag.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        drag.connect("button-press-event", self.drag)
        header.pack_start(drag, True, True, 0)
        hide = self.symbol_button("hide", "Sembunyikan", self.hide_window)
        settings = self.symbol_button("settings", "Pengaturan")
        quit_button = self.symbol_button("exit", "Keluar", lambda _button: self.quit())
        for button in (hide, settings, quit_button):
            header.pack_start(button, False, False, 0)
        box.pack_start(header, False, False, 0)

        popover = Gtk.Popover.new(settings)
        popover.set_name("bat07-settings")
        settings.connect("toggled", self.toggle_settings, popover)
        popover.connect("closed", lambda _popover: settings.set_active(False))
        controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=10)
        controls.pack_start(label("Opasitas", "section"), False, False, 0)
        opacity = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.45, 1, 0.05)
        opacity.set_size_request(135, -1)
        opacity.set_value(0.95)
        opacity.set_draw_value(False)
        opacity.get_accessible().set_name("Opasitas")
        opacity.connect("value-changed", lambda scale: self.window.set_opacity(scale.get_value()))
        self.window.set_opacity(opacity.get_value())
        controls.pack_start(opacity, False, False, 0)
        popover.add(controls)
        controls.show_all()

    def build_gauges(self, box):
        row = Gtk.Box(homogeneous=True, spacing=7)
        for kind, description in (("SOH", "Kesehatan baterai"), ("SOC", "Isi baterai")):
            card = panel()
            card.pack_start(label(description, "muted", "small", xalign=0.5), False, False, 0)
            overlay = Gtk.Overlay(halign=Gtk.Align.CENTER)
            image = Gtk.Image()
            image.set_size_request(GAUGE_SIZE, GAUGE_SIZE)
            overlay.add(image)
            center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            center.pack_start(label(kind, "muted", "small", xalign=0.5), False, False, 0)
            value = label("—", "gauge-value", xalign=0.5)
            center.pack_start(value, False, False, 0)
            overlay.add_overlay(center)
            overlay.set_overlay_pass_through(center, True)
            card.pack_start(overlay, False, False, 0)
            condition = label("Tidak tersedia", "small", xalign=0.5)
            card.pack_start(condition, False, False, 0)
            self.gauges[kind] = (image, value, condition)
            row.pack_start(card, True, True, 0)
        box.pack_start(row, False, False, 0)

    def build_telemetry(self, box):
        card = panel()
        card.pack_start(label("Telemetri", "section"), False, False, 0)
        rows = Gtk.Grid(column_spacing=10, row_spacing=2)
        for index, (key, title) in enumerate((
            ("temperature", "Suhu"), ("capacity", "Kapasitas aktual / desain"),
            ("voltage", "Tegangan"), ("current", "Arus"),
            ("ac", "Daya AC"), ("charging", "Status pengisian")
        )):
            name = label(title, "muted", xalign=0)
            name.set_hexpand(True)
            value = label("—", "reading", xalign=1)
            rows.attach(name, 0, index, 1, 1)
            rows.attach(value, 1, index, 1, 1)
            self.labels[key] = value
        self.labels["capacity_name"] = rows.get_child_at(0, 1)
        card.pack_start(rows, False, False, 0)
        box.pack_start(card, False, False, 0)

    def build_protection(self, box):
        card = panel()
        row = Gtk.Box(spacing=5)
        row.pack_start(label("Proteksi pengisian", "section"), True, True, 0)
        self.labels["target"] = label("Target —", "small", "muted", xalign=1)
        row.pack_end(self.labels["target"], False, False, 0)
        card.pack_start(row, False, False, 0)
        self.scale = Gtk.Image(halign=Gtk.Align.CENTER)
        self.scale.set_size_request(SCALE_WIDTH, SCALE_HEIGHT)
        card.pack_start(self.scale, False, False, 0)

        axis = Gtk.Box(homogeneous=True)
        axis.pack_start(label("0%", "small", "muted"), True, True, 0)
        self.labels["scale_soc"] = label("SOC —", "small", xalign=0.5)
        axis.pack_start(self.labels["scale_soc"], True, True, 0)
        axis.pack_start(label("100%", "small", "muted", xalign=1), True, True, 0)
        card.pack_start(axis, False, False, 0)
        self.labels["deviation"] = label("Deviasi —", "small")
        self.labels["mode"] = label("Mode —", "small", "muted")
        self.labels["mode"].set_line_wrap(True)
        card.pack_start(self.labels["deviation"], False, False, 0)
        card.pack_start(self.labels["mode"], False, False, 0)
        box.pack_start(card, False, False, 0)

    def build_history(self, box):
        card = panel()
        row = Gtk.Box(spacing=5)
        row.pack_start(label("Histori SOH", "section"), True, True, 0)
        segments = Gtk.Box()
        segments.get_style_context().add_class("period")
        group = None
        for key, caption in PERIOD_LABELS.items():
            control = Gtk.RadioButton.new_with_label_from_widget(group, caption)
            control.set_mode(False)
            control.get_accessible().set_name(f"Histori {key}")
            if group is None:
                group = control
            control.connect("toggled", self.change_period, key)
            segments.pack_start(control, False, False, 0)
        row.pack_end(segments, False, False, 0)
        card.pack_start(row, False, False, 0)
        self.graph = Gtk.Image(halign=Gtk.Align.CENTER)
        self.graph.get_accessible().set_name("Grafik histori SOH")
        self.graph.set_size_request(WIDTH, HEIGHT + TIME_HEIGHT)
        card.pack_start(self.graph, False, False, 0)
        box.pack_start(card, False, False, 0)

    def build_footer(self, box):
        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.labels["backend"] = label("BAT-05 —", "small")
        self.labels["alert"] = label("Alert —", "small")
        self.labels["alert"].set_line_wrap(True)
        self.labels["alert"].set_max_width_chars(48)

        # A fixed-height row repaints changed cells without changing the dashboard layout.
        self.clock_store = Gtk.ListStore(str, str, str)
        self.clock_row = self.clock_store.append(("Usia sampel —", "SYSFS —", "#a8b7c5"))
        clock = Gtk.TreeView(model=self.clock_store, headers_visible=False, can_focus=False)
        clock.set_name("bat07-clock")
        clock.get_accessible().set_name("Usia sampel dan waktu SYSFS")
        clock.get_selection().set_mode(Gtk.SelectionMode.NONE)
        for title, index, expand in (("Usia sampel", 0, True), ("SYSFS", 1, False)):
            cell = Gtk.CellRendererText(xalign=0 if expand else 1, xpad=0, ypad=0)
            if not expand:
                cell.set_property("foreground", "#a8b7c5")
            column = Gtk.TreeViewColumn(title, cell, text=index)
            if expand:
                column.add_attribute(cell, "foreground", 2)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width(96)
            column.set_expand(expand)
            clock.append_column(column)
        clock.set_fixed_height_mode(True)
        for item in (self.labels["backend"], clock, self.labels["alert"]):
            footer.pack_start(item, False, False, 0)
        box.pack_start(footer, False, False, 0)

    def drag(self, _widget, event):
        if event.button == 1:
            self.window.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        return False

    def place_x11(self, _window):
        if getattr(self, "placed", False):
            return
        display = self.window.get_display()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor:
            area = monitor.get_workarea()
            width, _ = self.window.get_size()
            self.window.move(max(area.x, area.x + area.width - width - 16), area.y + 16)
            self.placed = True

    def hide_window(self, *_):
        self.window.hide()
        return True

    @staticmethod
    def set_text(field, text):
        if field.get_text() != text:
            field.set_text(text)

    def set_tone(self, field, tone):
        before = self.tones.get(field)
        if before == tone:
            return
        style = field.get_style_context()
        if before in TONES:
            style.remove_class(before)
        style.add_class(tone)
        self.tones[field] = tone

    def set_image(self, key, image, width, height, painter, *args):
        if self.images.get(key) == args:
            return
        self.put_rgb(image, width, height, raster(width, height, painter, *args))
        self.images[key] = args

    @staticmethod
    def put_rgb(image, width, height, pixels):
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(pixels), GdkPixbuf.Colorspace.RGB, False, 8, width, height, 3 * width)
        image.set_from_pixbuf(pixbuf)

    def refresh(self):
        values = live()
        now = values["timestamp"]
        if not self.backend or now - self.backend_at >= 30 or now < self.last_tick or now - self.last_tick > 6:
            self.backend = self.backend_cache.load(int(now))
            self.backend_at = now
            self.history_layouts.clear()
            self.draw()
        self.last_tick = now
        self.update_live(values)
        self.update_protection(values["charge"], self.backend.firmware)
        self.update_footer(now)
        return GLib.SOURCE_CONTINUE

    def update_live(self, values):
        for kind, number in (("SOH", values["soh"]), ("SOC", values["charge"])):
            image, field, condition = self.gauges[kind]
            text, description, tone, fraction = gauge_reading(number, kind, values["health"])
            self.set_text(field, text)
            self.set_text(condition, description)
            self.set_tone(condition, tone)
            self.set_image(kind, image, GAUGE_SIZE, GAUGE_SIZE, paint_gauge, fraction, tone)

        capacity_name = "Kapasitas aktual / desain"
        if values["estimated_wh"]:
            capacity_name += "\n(estimasi)"
        readings = {
            "temperature": formatted(values["temperature"], "{:.1f} °C"),
            "capacity": " / ".join(formatted(values[key], "{:.2f}") for key in ("capacity", "design"))
                        + (" Wh" if values["capacity"] is not None or values["design"] is not None else ""),
            "capacity_name": capacity_name,
            "voltage": formatted(values["voltage"], "{:.3f} V"),
            "current": formatted(values["current"], "{:.3f} A"),
            "ac": {0: "Terputus", 1: "Terhubung"}.get(values["ac"], "—"),
            "charging": values["status"] or "—",
        }
        for key, text in readings.items():
            self.set_text(self.labels[key], text)

    def update_protection(self, soc, firmware):
        limits, target, deviation, tone = charge_target(firmware, soc)
        self.set_text(self.labels["target"], target)
        self.set_text(self.labels["scale_soc"], f"SOC {formatted(soc, '{}%')}")
        self.set_text(self.labels["deviation"], deviation)
        self.set_tone(self.labels["deviation"], tone)
        mode = firmware.get("PrimaryBattChargeCfg") or "—"
        advanced = firmware.get("AdvBatteryChargeCfg") or "—"
        self.set_text(self.labels["mode"], f"Mode {mode}  ·  Lanjutan {advanced}")
        self.set_image("scale", self.scale, SCALE_WIDTH, SCALE_HEIGHT, paint_scale, limits, soc)

    def update_footer(self, now):
        backend = self.backend
        age = freshness(backend.timestamp, now)
        self.set_text(self.labels["backend"], f"BAT-05 · {backend.status}")
        self.set_tone(self.labels["backend"], status_tone(backend, age))
        color = "#ffbf71" if age.startswith("STALE") else "#a8b7c5"
        clock = (age, f"SYSFS {stamp(now)}", color)
        if clock != self.clock_values:
            self.clock_store.set(self.clock_row, 0, clock[0], 1, clock[1], 2, clock[2])
            self.clock_values = clock

        alerts = [f"{level.upper()} {key}" for key, level, _ in backend.alerts]
        summary = " · ".join(alerts[:3])
        if len(alerts) > 3:
            summary += f"  +{len(alerts) - 3}"
        severity = {level for _, level, _ in backend.alerts}
        tone = ("danger" if "high" in severity else "warning" if "warning" in severity
                else "good" if backend.timestamp is not None and not severity else "muted")
        field = self.labels["alert"]
        self.set_text(field, summary or ("Alert —" if backend.timestamp is None else "Tanpa alert aktif"))
        self.set_tone(field, tone)
        tooltip = "\n".join(f"{key}: {detail}" for key, _, detail in backend.alerts) or None
        if field.get_tooltip_text() != tooltip:
            field.set_tooltip_text(tooltip)

    def change_period(self, button, key):
        if button.get_active():
            self.selected_period = key
            if self.backend is not None:
                self.draw()

    def draw(self):
        span = PERIODS[self.selected_period]
        if span not in self.history_layouts:
            samples = self.backend_cache.history(int(self.backend_at), span)
            self.history_layouts[span] = history_layout(samples, self.backend_at, span)
        drawing = self.history_layouts[span]
        if self.images.get("history") == drawing:
            return
        points, ticks, times = drawing
        plot = self.history_pixels("plot", HEIGHT, paint_history, points, ticks, HISTORY_DIVISIONS)
        axis = self.history_pixels("axis", TIME_HEIGHT, paint_history_time, times, HISTORY_DIVISIONS)
        self.put_rgb(self.graph, WIDTH, HEIGHT + TIME_HEIGHT, plot + axis)
        self.images["history"] = drawing

    def history_pixels(self, key, height, painter, *args):
        previous = self.history_rasters.get(key)
        if previous is not None and previous[0] == args:
            return previous[1]
        pixels = raster(WIDTH, height, painter, *args)
        self.history_rasters[key] = (args, pixels)
        return pixels


if __name__ == "__main__":
    GLib.set_prgname(APP_ID)
    Gtk.init_check()
    if Gdk.Display.get_default() is None:
        print("BAT-07: GTK tidak dapat terhubung ke compositor", file=sys.stderr)
        sys.exit(1)
    sys.exit(Widget().run(sys.argv))
