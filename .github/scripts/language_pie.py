#!/usr/bin/env python3
"""Render the WakaTime top-languages pie chart as light and dark SVGs.

Reads tab-separated rows (name, percent, hex colour, simple-icons slug, logo
colour) on stdin, largest first, and writes assets/languages-{light,dark}.svg.
Colours, names and logos match the shields.io badges shown under the chart;
whatever is left of 100% becomes a gray "Other" slice so slices are true shares.
"""
import math
import re
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

# Pinned so logos only change on purpose; slugs are the ones shields.io uses.
ICON_URL = "https://cdn.jsdelivr.net/npm/simple-icons@15.0.0/icons/{}.svg"
OTHER_COLOR = "6E7781"
# Text colours and the slice gap follow GitHub's own light/dark palettes.
# The dark ring keeps black brand colours (Markdown, JSON) visible.
THEMES = {
    "light": {"text": "#1f2328", "muted": "#59636e", "gap": "#ffffff", "ring": None},
    "dark": {"text": "#f0f6fc", "muted": "#9198a1", "gap": "#0d1117", "ring": "#3d444d"},
}
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
R = 150              # pie radius
CALLOUT_GAP = 28     # pie edge -> outside label
CALLOUT_ROOM = 160   # width reserved for an outside label on each side
CALLOUT_ROW = 22     # min vertical spacing between outside labels
WIDTH = 2 * (R + CALLOUT_GAP + CALLOUT_ROOM)
HEIGHT = 2 * R + 60
LOGO = 16


def icon_path(slug, cache={}):
    if slug and slug not in cache:
        try:
            with urllib.request.urlopen(ICON_URL.format(slug), timeout=10) as resp:
                match = re.search(r'<path d="([^"]+)"', resp.read().decode())
            cache[slug] = match.group(1) if match else None
        except OSError as err:
            print(f"::warning::No logo for {slug}: {err}")
            cache[slug] = None
    return cache.get(slug)


def point(cx, cy, r, angle):
    return cx + r * math.cos(angle), cy + r * math.sin(angle)


def text_width(text, size):
    # No font metrics here; ~0.58em per character covers semibold sans.
    return len(text) * size * 0.58


def logo(s, x, y, size, color):
    d = icon_path(s["logo"])
    if not d:
        return ""
    return f'<path transform="translate({x:.2f},{y:.2f}) scale({size / 24})" d="{d}" fill="{color}"/>'


def fits_in_slice(box_w, box_h, lx, ly, cx, cy, start, sweep):
    """Whether a box centred on (lx, ly) lies inside the slice, with a margin."""
    for dx in (-box_w / 2, box_w / 2):
        for dy in (-box_h / 2, box_h / 2):
            x, y = lx + dx - cx, ly + dy - cy
            r = math.hypot(x, y)
            if r > R - 6:
                return False
            if r < 6:
                continue
            margin = math.asin(min(1, 5 / r))
            offset = (math.atan2(y, x) - start) % (2 * math.pi)
            if not margin <= offset <= sweep - margin:
                return False
    return True


def inside_label(s, cx, cy, start, sweep):
    """Logo, name and percent stacked inside the slice, or None if they don't fit."""
    has_logo = bool(icon_path(s["logo"]))
    pct = f'{s["percent"]:.1f}%'
    box_w = max(text_width(s["name"], 12), text_width(pct, 11), LOGO if has_logo else 0)
    box_h = (LOGO + 3 if has_logo else 0) + 14 + 13
    mid = start + sweep / 2
    # Try along the slice's centre line, from the comfortable middle outwards.
    for f in sorted((i / 40 for i in range(16, 35)), key=lambda f: abs(f - 0.62)):
        lx, ly = point(cx, cy, R * f, mid)
        if fits_in_slice(box_w, box_h, lx, ly, cx, cy, start, sweep):
            top = ly - box_h / 2
            parts = []
            if has_logo:
                parts.append(logo(s, lx - LOGO / 2, top, LOGO, s["ink"]))
                top += LOGO + 3
            attrs = f'x="{lx:.2f}" fill="{s["ink"]}" text-anchor="middle" dominant-baseline="central"'
            parts.append(f'<text {attrs} y="{top + 7:.2f}" font-size="12" font-weight="600">{escape(s["name"])}</text>')
            parts.append(f'<text {attrs} y="{top + 20.5:.2f}" font-size="11">{pct}</text>')
            return parts
    return None


def callouts(pending, cx, cy, t):
    """Labels outside the pie, with a leader line, for slices too thin for text.

    Each is a badge-style swatch (brand colour + logo), the name and percent.
    Labels on each side are pushed apart vertically so they never overlap.
    """
    out = []
    for side in (1, -1):
        group = sorted((p for p in pending if (math.cos(p[1]) >= 0) == (side == 1)),
                       key=lambda p: point(cx, cy, R, p[1])[1])
        ys = []
        for s, mid in group:
            y = point(cx, cy, R + 12, mid)[1]
            ys.append(max(y, ys[-1] + CALLOUT_ROW) if ys else y)
        overflow = (ys[-1] + 12 - HEIGHT) if ys else 0
        ys = [y - max(0, overflow) for y in ys]

        ring = f' stroke="{t["ring"]}"' if t["ring"] else ""
        for (s, mid), y in zip(group, ys):
            ax, ay = point(cx, cy, R - 2, mid)
            ex = point(cx, cy, R + 12, mid)[0]
            lx = cx + side * (R + CALLOUT_GAP)
            out.append(
                f'<polyline points="{ax:.2f},{ay:.2f} {ex:.2f},{y:.2f} {lx - side * 4:.2f},{y:.2f}" '
                f'fill="none" stroke="{t["muted"]}"/>'
            )
            # Swatch sits against the line; text runs away from the pie.
            sx = lx if side == 1 else lx - 18
            out.append(f'<rect x="{sx:.2f}" y="{y - 9:.2f}" width="18" height="18" rx="3" fill="#{s["color"]}"{ring}/>')
            out.append(logo(s, sx + 3, y - 6, 12, s["ink"]))
            tx = lx + side * 24
            anchor = "start" if side == 1 else "end"
            out.append(
                f'<text x="{tx:.2f}" y="{y:.2f}" text-anchor="{anchor}" dominant-baseline="central">'
                f'<tspan fill="{t["text"]}">{escape(s["name"])}</tspan>'
                f'<tspan fill="{t["muted"]}"> {s["percent"]:.2f}%</tspan></text>'
            )
    return out


def render(slices, theme):
    t = THEMES[theme]
    cx, cy = WIDTH / 2, HEIGHT / 2
    title = ", ".join(f"{s['name']} {s['percent']:.2f}%" for s in slices)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" font-family="{FONT}" font-size="13">',
        f"<title>Top languages by coding time: {escape(title)}</title>",
    ]

    labels, pending = [], []
    angle = -math.pi / 2  # start at 12 o'clock, go clockwise
    for s in slices:
        sweep = 2 * math.pi * s["percent"] / 100
        if s["percent"] >= 99.99:
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#{s["color"]}"/>')
        else:
            x0, y0 = point(cx, cy, R, angle)
            x1, y1 = point(cx, cy, R, angle + sweep)
            large = 1 if sweep > math.pi else 0
            out.append(
                f'<path d="M{cx:.2f},{cy:.2f} L{x0:.2f},{y0:.2f} '
                f'A{R},{R} 0 {large} 1 {x1:.2f},{y1:.2f} Z" fill="#{s["color"]}" '
                f'stroke="{t["gap"]}" stroke-width="2" stroke-linejoin="round"/>'
            )
        inside = inside_label(s, cx, cy, angle, sweep)
        if inside:
            labels += inside
        else:
            pending.append((s, angle + sweep / 2))
        angle += sweep
    if t["ring"]:
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{t["ring"]}"/>')

    out += labels + callouts(pending, cx, cy, t)
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    slices = []
    for line in sys.stdin:
        name, percent, color, logo, ink = line.rstrip("\n").split("\t")
        slices.append({"name": name, "percent": float(percent), "color": color, "logo": logo, "ink": ink})
    if not slices:
        sys.exit("no languages on stdin")
    other = round(100 - sum(s["percent"] for s in slices), 2)
    if other > 0:
        slices.append({"name": "Other", "percent": other, "color": OTHER_COLOR, "logo": "", "ink": "white"})

    Path("assets").mkdir(exist_ok=True)
    for theme in THEMES:
        Path(f"assets/languages-{theme}.svg").write_text(render(slices, theme))


if __name__ == "__main__":
    main()
