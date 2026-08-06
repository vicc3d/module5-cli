"""Two glyph sets: one Unicode, one plain ASCII.

Box-drawing characters (U+2500…) and blocks (U+2588…) have "Neutral" width and
render at a single cell's advance in any modern terminal, so they're safe for
the frame and the board. Arrows, the middle dot, and angle quotes, on the
other hand, have "Ambiguous" width: some terminals (Terminal.app among them)
paint them at double width and throw the box's right edge off by a column.
That's why the game only starts with the Unicode set when the environment
looks modern, and falls back to ASCII on plain consoles (TERM=linux, dumb) or
if forced with MODULE5_ASCII=1 / --ascii.
"""

import os

UNICODE = {
    # frame
    "tl": "┌", "tr": "┐", "bl": "└", "br": "┘",
    "h": "─", "v": "│",
    "lt": "├", "rt": "┤", "tt": "┬", "bt": "┴",
    # double frame (board and modals)
    "dtl": "╔", "dtr": "╗", "dbl": "╚", "dbr": "╝",
    "dh": "═", "dv": "║",
    # blocks
    "full": "█", "upper": "▀", "lower": "▄",
    "shade": "░", "shade2": "▒",
    # marks
    "dot": "·",
    "empty_cell": "·",
    "sep": " · ",
    "ok": "✓",
    "bad": "✕",
    "arrow_r": "→",
    "arrows": "←↑↓→",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
    "enter": "⏎",
    "quote_l": "«", "quote_r": "»",
    "bullet": "•",
    "lock": "─",
    "spinner": "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏",
}

ASCII = {
    "tl": "+", "tr": "+", "bl": "+", "br": "+",
    "h": "-", "v": "|",
    "lt": "+", "rt": "+", "tt": "+", "bt": "+",
    "dtl": "+", "dtr": "+", "dbl": "+", "dbr": "+",
    "dh": "=", "dv": "|",
    "full": "#", "upper": '"', "lower": "_",
    "shade": ".", "shade2": ":",
    "dot": ".",
    "empty_cell": ".",
    "sep": " . ",
    "ok": "*",
    "bad": "x",
    "arrow_r": "->",
    "arrows": "<^v>",
    "up": "^", "down": "v", "left": "<", "right": ">",
    "enter": "RET",
    "quote_l": '"', "quote_r": '"',
    "bullet": "*",
    "lock": "-",
    "spinner": "|/-\\",
}

_g = dict(UNICODE)


def looks_modern():
    if os.environ.get("MODULE5_ASCII"):
        return False
    term = (os.environ.get("TERM") or "").lower()
    if term in ("", "dumb", "linux", "vt100", "vt220", "ansi"):
        return False
    if os.environ.get("COLORTERM") or os.environ.get("TERM_PROGRAM"):
        return True
    return any(k in term for k in ("256color", "kitty", "alacritty", "wezterm", "ghostty", "xterm", "screen", "tmux", "rxvt"))


def use_ascii(flag):
    global _g
    _g = dict(ASCII if flag else UNICODE)


def g(key):
    return _g[key]


use_ascii(not looks_modern())
