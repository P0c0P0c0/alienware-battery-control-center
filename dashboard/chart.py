"""Cached drawing inputs and native Cairo rasters for the dashboard."""
from datetime import datetime
from math import isfinite, pi
from sys import byteorder

import cairo

WIDTH, HEIGHT, TIME_HEIGHT = 330, 96, 25
HISTORY_DIVISIONS = (51, (51 + WIDTH - 13) / 2, WIDTH - 13)
GAUGE_SIZE = 106
SYMBOL_SIZE = 16
SCALE_WIDTH, SCALE_HEIGHT = 318, 24
PANEL_RGB = (20, 30, 40)
COLORS = {
    "cyan": (0.34, 0.87, 0.98),
    "good": (0.42, 0.88, 0.66),
    "warning": (1.0, 0.74, 0.42),
    "danger": (1.0, 0.50, 0.54),
    "muted": (0.59, 0.66, 0.73),
    "track": (0.17, 0.22, 0.29),
    "grid": (0.21, 0.27, 0.34),
}


def color(context, key):
    context.set_source_rgb(*COLORS[key])


def raster(width, height, painter, *args):
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    context = cairo.Context(surface)
    context.set_source_rgb(*(channel / 255 for channel in PANEL_RGB))
    context.paint()
    painter(context, *args)
    surface.flush()
    source = surface.get_data()
    # Cairo stores native-endian xRGB words. GdkPixbuf expects packed RGB bytes.
    offsets = (2, 1, 0) if byteorder == "little" else (1, 2, 3)
    pixels = bytearray(width * height * 3)
    for channel, offset in enumerate(offsets):
        pixels[channel::3] = source[offset::4]
    return bytes(pixels)


def button_symbol(name):
    """Draw a 16 px Cairo alpha mask and pack it as straight RGBA."""
    size = SYMBOL_SIZE
    surface = cairo.ImageSurface(cairo.FORMAT_A8, size, size)
    context = cairo.Context(surface)
    context.set_source_rgba(1, 1, 1, 1)
    context.set_line_width(1.5)
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    context.set_line_join(cairo.LINE_JOIN_ROUND)
    if name == "hide":
        context.move_to(3.5, 10.5)
        context.line_to(12.5, 10.5)
    elif name == "settings":
        for x, y in ((5, 4.5), (11, 8), (7, 11.5)):
            context.move_to(2.5, y)
            context.line_to(x - 1.25, y)
            context.move_to(x + 1.25, y)
            context.line_to(13.5, y)
            context.move_to(x, y - 1.2)
            context.line_to(x, y + 1.2)
    elif name == "exit":
        context.move_to(4.25, 4.25)
        context.line_to(11.75, 11.75)
        context.move_to(11.75, 4.25)
        context.line_to(4.25, 11.75)
    else:
        raise ValueError(f"Unknown button symbol: {name}")
    context.stroke()
    surface.flush()

    rgba = bytearray(bytes((172, 226, 241, 0)) * (size * size))
    mask = surface.get_data()
    stride = surface.get_stride()
    for y in range(size):
        rgba[y * size * 4 + 3:(y + 1) * size * 4:4] = mask[y * stride:y * stride + size]
    return bytes(rgba)


def gauge_reading(value, kind, health=None):
    if value is None or not isfinite(value):
        return "—", "Tidak tersedia", "muted", None
    if kind == "SOH":
        if value < 60:
            condition, tone = "Perlu perhatian", "danger"
        elif value < 80 or health not in (None, "Good"):
            condition, tone = "Kapasitas menurun" if value < 80 else "Periksa baterai", "warning"
        else:
            condition, tone = "Sehat", "good"
        text = f"{value:.2f}%"
    else:
        if value <= 10:
            condition, tone = "Sangat rendah", "danger"
        elif value <= 20:
            condition, tone = "Rendah", "warning"
        elif value >= 100:
            condition, tone = "Penuh", "good"
        else:
            condition, tone = "Terisi", "good"
        text = f"{value:.0f}%"
    # Match the displayed precision before comparing whether a gauge changed.
    fraction = min(100, max(0, float(text[:-1]))) / 100
    return text, condition, tone, fraction


def paint_gauge(context, fraction, tone):
    center = GAUGE_SIZE / 2
    context.set_line_width(6)
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    color(context, "track")
    context.arc(center, center, center - 7, 0, 2 * pi)
    context.stroke()
    if fraction:
        color(context, "cyan" if tone == "good" else tone)
        context.arc(center, center, center - 7, -pi / 2, -pi / 2 + 2 * pi * fraction)
        context.stroke()


def charge_target(firmware, soc):
    try:
        start, stop = (int(firmware[key]) for key in ("CustomChargeStart", "CustomChargeStop"))
        if not 0 <= start < stop <= 100:
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, "Target —", "Deviasi —", "muted"
    limits = (start, stop)
    if soc is None:
        return limits, f"Target {start}–{stop}%", "Deviasi —", "muted"
    if soc < start:
        return limits, f"Target {start}–{stop}%", f"{start - soc} poin di bawah", "warning"
    if soc > stop:
        return limits, f"Target {start}–{stop}%", f"{soc - stop} poin di atas", "warning"
    return limits, f"Target {start}–{stop}%", "Dalam target", "good"


def paint_scale(context, limits, soc):
    start, length = 6, SCALE_WIDTH - 12
    context.set_line_width(6)
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    color(context, "track")
    context.move_to(start, 12)
    context.line_to(start + length, 12)
    context.stroke()
    if limits:
        low, high = limits
        color(context, "good")
        context.move_to(start + length * low / 100, 12)
        context.line_to(start + length * high / 100, 12)
        context.stroke()
    if soc is not None:
        x = start + length * soc / 100
        color(context, "cyan")
        context.move_to(x, 3)
        context.line_to(x, 21)
        context.set_line_width(3)
        context.stroke()


def history_layout(samples, end, span):
    valid = [(ts, soh) for ts, soh in samples if end - span <= ts <= end and isfinite(soh)]
    times = tuple(datetime.fromtimestamp(end - span * step).strftime(
        "%H:%M" if span == 86400 else "%d/%m") for step in (1, 0.5, 0))
    if not valid:
        return (), (), times
    values = [soh for _, soh in valid]
    low, high = min(values) - 0.25, max(values) + 0.25
    ticks = tuple(f"{value:.1f}%" for value in (high, (low + high) / 2, low))
    points = []
    previous = None
    for ts, soh in valid:
        x = round(51 + (WIDTH - 64) * (ts - end + span) / span)
        y = round(12 + 80 * (high - soh) / (high - low))
        connected = previous is not None and ts - previous <= max(900, span // 150)
        points.append((x, y, connected))
        previous = ts
    return tuple(points), ticks, times


def history_label(context, text, x, y, alignment=0):
    extents = context.text_extents(text)
    color(context, "muted")
    context.move_to(x - alignment * extents.x_advance, y)
    context.show_text(text)


def paint_history(context, points, ticks, divisions):
    context.select_font_face("Sans")
    context.set_font_size(10)
    left, right = 51, WIDTH - 13
    for row, y in enumerate((12, 52, 92)):
        color(context, "grid")
        context.set_line_width(1)
        context.move_to(left, y + 0.5)
        context.line_to(right, y + 0.5)
        context.stroke()
        if ticks:
            history_label(context, ticks[row], left - 7, y + 3, 1)
    for x in divisions:
        color(context, "grid")
        context.move_to(x + 0.5, 12)
        context.line_to(x + 0.5, 92)
        context.stroke()
    if not points:
        history_label(context, "Histori SOH belum tersedia", (left + right) / 2, 55, 0.5)
        return
    color(context, "cyan")
    context.set_line_width(1.6)
    for x, y, connected in points:
        if connected:
            context.line_to(x, y)
        else:
            context.move_to(x, y)
    context.stroke()
    for x, y, _ in points:
        context.new_sub_path()
        context.arc(x, y, 2, 0, 2 * pi)
    context.fill()


def paint_history_time(context, times, divisions):
    context.select_font_face("Sans")
    context.set_font_size(10)
    for text, x, alignment in zip(times, divisions, (0, 0.5, 1)):
        history_label(context, text, x, 111 - HEIGHT, alignment)
