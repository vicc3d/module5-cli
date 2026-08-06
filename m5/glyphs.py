"""Dos juegos de glifos: uno Unicode y uno ASCII puro.

Los caracteres de caja (U+2500…) y los bloques (U+2588…) tienen ancho
"Neutral" y se dibujan con un solo avance en cualquier terminal moderna, asi
que son seguros para el marco y el tablero. En cambio las flechas, el punto
medio y las comillas angulares tienen ancho "Ambiguous": algunas terminales
(Terminal.app entre ellas) las pintan al doble de ancho y corren el borde
derecho de la caja una columna. Por eso el juego arranca con el set Unicode
solo cuando el entorno se ve moderno, y cae al ASCII en consolas sobrias
(TERM=linux, dumb) o si se fuerza con MODULE5_ASCII=1 / --ascii.
"""

import os

UNICODE = {
    # marco
    "tl": "┌", "tr": "┐", "bl": "└", "br": "┘",
    "h": "─", "v": "│",
    "lt": "├", "rt": "┤", "tt": "┬", "bt": "┴",
    # marco doble (tablero y modales)
    "dtl": "╔", "dtr": "╗", "dbl": "╚", "dbr": "╝",
    "dh": "═", "dv": "║",
    # bloques
    "full": "█", "upper": "▀", "lower": "▄",
    "shade": "░", "shade2": "▒",
    # marcas
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
