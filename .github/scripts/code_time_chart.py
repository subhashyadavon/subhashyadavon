#!/usr/bin/env python3
"""Render monthly WakaTime coding time as light and dark bar-chart SVGs.

Reads tab-separated rows (YYYY-MM, seconds) on stdin, oldest first, and
writes assets/code-time-{light,dark}.svg, styled to sit under the language pie.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from language_pie import FONT, THEMES, WIDTH

# One colour per calendar month (Jan..Dec), so a month keeps its colour as
# the chart grows. Each clears 3:1 on GitHub's light and dark backgrounds and
# neighbouring months (Dec->Jan too) are far apart in hue and lightness;
# every bar is labelled with its month, so colour never has to identify it.
MONTH_COLORS = [
    "#ba5277", "#40a35c", "#8864c0", "#ab8704", "#0c82bf", "#d36757",
    "#018e7d", "#bb6ab4", "#718509", "#6b86e1", "#b36303", "#059eb1",
]
HEIGHT = 250
PAD = 16
BAR_MAX_W = 24     # thin columns; the rest of each slot stays air
PLOT_TOP = 72      # below the headline, with room for the tallest value label
BASELINE = HEIGHT - 44


def duration(seconds, long=False):
    h, m = divmod(round(seconds / 60), 60)
    if long:
        return f"{h} hrs {m} mins"
    return f"{h}h {m}m" if h else f"{m}m"


def column(x, w, h):
    """Column path: square at the baseline, 4px rounded at the top."""
    top = BASELINE - h
    r = min(4, h, w / 2)
    return (
        f"M{x:.2f},{BASELINE} V{top + r:.2f} Q{x:.2f},{top:.2f} {x + r:.2f},{top:.2f} "
        f"H{x + w - r:.2f} Q{x + w:.2f},{top:.2f} {x + w:.2f},{top + r:.2f} V{BASELINE} Z"
    )


def render(months, theme):
    t = THEMES[theme]
    dates = [datetime.strptime(m, "%Y-%m") for m, _ in months]
    total = sum(s for _, s in months)
    peak = max(s for _, s in months) or 1
    current = datetime.now(timezone.utc).strftime("%Y-%m")
    slot = (WIDTH - 2 * PAD) / len(months)
    bar_w = min(BAR_MAX_W, slot * 0.6)
    title = ", ".join(f"{d:%B %Y} {duration(s)}" for d, (_, s) in zip(dates, months))
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" font-family="{FONT}" font-size="12">',
        f"<title>Coding time per month: {escape(title)}</title>",
        f'<text x="{PAD}" y="32" fill="{t["text"]}" font-size="20" font-weight="600">'
        f'{duration(total, long=True)}</text>',
        f'<line x1="{PAD}" x2="{WIDTH - PAD}" y1="{BASELINE}" y2="{BASELINE}" stroke="{t["axis"]}"/>',
    ]

    for i, (date, (month, seconds)) in enumerate(zip(dates, months)):
        x = PAD + slot * i + (slot - bar_w) / 2
        mid = x + bar_w / 2
        h = (BASELINE - PLOT_TOP) * seconds / peak
        partial = month == current
        if h >= 0.5:
            # The month still in progress is drawn lighter and marked "so far".
            opacity = ' fill-opacity="0.5"' if partial else ""
            out.append(f'<path d="{column(x, bar_w, h)}" fill="{MONTH_COLORS[date.month - 1]}"{opacity}/>')
        value = duration(seconds) if slot >= 56 else f"{round(seconds / 3600)}h"
        out.append(
            f'<text x="{mid:.2f}" y="{BASELINE - h - 8:.2f}" fill="{t["text"]}" font-weight="600" '
            f'text-anchor="middle">{value}</text>'
        )
        out.append(
            f'<text x="{mid:.2f}" y="{BASELINE + 18}" fill="{t["muted"]}" text-anchor="middle">{date:%b}</text>'
        )
        note = "so far" if partial else (f"{date:%Y}" if i == 0 or date.month == 1 else "")
        if note:
            out.append(
                f'<text x="{mid:.2f}" y="{BASELINE + 33}" fill="{t["muted"]}" font-size="11" '
                f'text-anchor="middle">{note}</text>'
            )

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    months = []
    for line in sys.stdin:
        month, seconds = line.rstrip("\n").split("\t")
        months.append((month, float(seconds)))
    if not months:
        sys.exit("no months on stdin")

    Path("assets").mkdir(exist_ok=True)
    for theme in THEMES:
        Path(f"assets/code-time-{theme}.svg").write_text(render(months, theme))


if __name__ == "__main__":
    main()
