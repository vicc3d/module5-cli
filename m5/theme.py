"""Temas visuales. Equivalen a los temas de la version web, traducidos a lo
que una terminal puede dar: neon sobre negro, fosforo verde, plano azul y uno
sin color para terminales sobrias o TERM=dumb.
"""

from .pieces import PIECE_COLORS, PIECE_NAMES
from .term import rgb, mix


class Theme:
    def __init__(self, key, desc_key, colors, tiles=True, piece_colors=None):
        self.key = key
        self.desc_key = desc_key
        self.tiles = tiles            # celdas como baldosas de color o como letras
        for name, value in colors.items():
            setattr(self, name, rgb(value) if isinstance(value, str) else value)
        self._pieces = {
            n: (rgb(c) if isinstance(c, str) else c)
            for n, c in (piece_colors or PIECE_COLORS).items()
        }

    def piece(self, name):
        return self._pieces.get(name, self.text)

    def dim_piece(self, name, t=0.62):
        """Version apagada del color de una pieza (bandeja, fantasma)."""
        color = self._pieces.get(name, self.text)
        if color is None or self.bg is None:
            return None  # tema sin color: se distingue por atributo, no por tono
        return mix(color, self.bg, t)

    def dim(self, color, t=0.5):
        if color is None or self.bg is None:
            return None
        return mix(color, self.bg, t)


_NEON = {
    "bg": "#08080b",
    "panel": "#0e0e13",
    "board_bg": "#0b0b10",
    "border": "#2a2a38",
    "border_hi": "#00e5ff",
    "text": "#c9c9d4",
    "text_dim": "#5a5a6e",
    "text_hi": "#f2f2f7",
    "accent": "#00e5ff",
    "accent2": "#ff2d78",
    "ok": "#35ff69",
    "bad": "#ff5349",
    "warn": "#ffe600",
    "empty": "#2e2e3c",
    "tile_text": "#08080b",
}

_GREEN = "#35ff69"
_ASCII = {
    **_NEON,
    "bg": "#000000",
    "panel": "#000000",
    "board_bg": "#000000",
    "border": "#1d7a34",
    "border_hi": _GREEN,
    "text": "#35ff69",
    "text_dim": "#1d7a34",
    "text_hi": "#b6ffc7",
    "accent": _GREEN,
    "accent2": "#b6ffc7",
    "empty": "#17561f",
    "tile_text": "#000000",
}

_BLUE = "#4d9fff"
_BLUEPRINT = {
    **_NEON,
    "bg": "#071426",
    "panel": "#0a1c33",
    "board_bg": "#08182c",
    "border": "#1f4a7a",
    "border_hi": "#8fc4ff",
    "text": "#bcd8f7",
    "text_dim": "#4a7096",
    "text_hi": "#eaf4ff",
    "accent": _BLUE,
    "accent2": "#8fc4ff",
    "ok": "#7fe0a8",
    "bad": "#ff8f80",
    "warn": "#ffd98f",
    "empty": "#1a3c5c",
    "tile_text": "#071426",
}

_MONO = {
    **_NEON,
    "bg": None,
    "panel": None,
    "board_bg": None,
    "border": None,
    "border_hi": None,
    "text": None,
    "text_dim": None,
    "text_hi": None,
    "accent": None,
    "accent2": None,
    "ok": None,
    "bad": None,
    "warn": None,
    "empty": None,
    "tile_text": None,
}


def _shades(base, lo=0.4, hi=1.0):
    """Doce tonos de un mismo color: para los temas monocromaticos, donde las
    piezas se distinguen por la letra y apenas por el brillo."""
    out = {}
    n = len(PIECE_NAMES)
    for i, name in enumerate(PIECE_NAMES):
        t = lo + (hi - lo) * (i / (n - 1))
        out[name] = mix("#000000", base, t)
    return out


THEMES = {
    "neon": Theme("neon", "theme_neon", _NEON, tiles=True),
    "ascii": Theme("ascii", "theme_ascii", _ASCII, tiles=False,
                   piece_colors=_shades(_GREEN, lo=0.45)),
    "blueprint": Theme("blueprint", "theme_blueprint", _BLUEPRINT, tiles=True,
                       piece_colors=_shades(_BLUE, lo=0.4)),
    "mono": Theme("mono", "theme_mono", _MONO, tiles=False,
                  piece_colors={n: None for n in PIECE_NAMES}),
}

THEME_ORDER = ["neon", "ascii", "blueprint", "mono"]


def get_theme(key, color_mode=None):
    theme = THEMES.get(key) or THEMES["neon"]
    # en una terminal sin color el tema pintado no sirve de nada
    if color_mode == "mono":
        return THEMES["mono"]
    return theme
