"""Los 12 pentominos (celdas (fila, columna)) y utilidades de orientacion.

Port directo de src/pieces.js de la version web: las mismas definiciones, el
mismo orden alfabetico y la misma paleta neon, para que un tablero se vea
igual en la terminal que en el navegador.
"""

PIECE_DEFS = {
    "F": ((0, 1), (0, 2), (1, 0), (1, 1), (2, 1)),
    "I": ((0, 0), (1, 0), (2, 0), (3, 0), (4, 0)),
    "L": ((0, 0), (1, 0), (2, 0), (3, 0), (3, 1)),
    "N": ((0, 1), (1, 1), (2, 0), (2, 1), (3, 0)),
    "P": ((0, 0), (0, 1), (1, 0), (1, 1), (2, 0)),
    "T": ((0, 0), (0, 1), (0, 2), (1, 1), (2, 1)),
    "U": ((0, 0), (0, 2), (1, 0), (1, 1), (1, 2)),
    "V": ((0, 0), (1, 0), (2, 0), (2, 1), (2, 2)),
    "W": ((0, 0), (1, 0), (1, 1), (2, 1), (2, 2)),
    "X": ((0, 1), (1, 0), (1, 1), (1, 2), (2, 1)),
    "Y": ((0, 1), (1, 0), (1, 1), (2, 1), (3, 1)),
    "Z": ((0, 0), (0, 1), (1, 1), (2, 1), (2, 2)),
}

PIECE_NAMES = list(PIECE_DEFS)

# Paleta neon sobre fondo negro: saturada pero sin estridencia.
PIECE_COLORS = {
    "F": "#ff2d78",
    "I": "#00e5ff",
    "L": "#ff9100",
    "N": "#35ff69",
    "P": "#ff54d7",
    "T": "#8c54ff",
    "U": "#00ffc8",
    "V": "#ffe600",
    "W": "#ff5349",
    "X": "#00a2ff",
    "Y": "#b4ff00",
    "Z": "#d10fff",
}

# Tecla por pieza, en el orden de PIECE_NAMES (igual que la bandeja web).
PIECE_KEYS = {
    "F": "1", "I": "2", "L": "3", "N": "4", "P": "5", "T": "6",
    "U": "7", "V": "8", "W": "9", "X": "0", "Y": "-", "Z": "=",
}


def normalize_cells(cells):
    """Traslada las celdas al origen y las ordena de forma canonica."""
    min_r = min(c[0] for c in cells)
    min_c = min(c[1] for c in cells)
    return tuple(sorted((r - min_r, c - min_c) for r, c in cells))


def rotate_cw(cells):
    return normalize_cells([(c, -r) for r, c in cells])


def flip_h(cells):
    return normalize_cells([(r, -c) for r, c in cells])


def orientations_of(cells):
    """Todas las orientaciones unicas: 4 rotaciones x 2 reflejos, deduplicadas."""
    seen = {}
    cur = normalize_cells(cells)
    for _ in range(2):
        for _ in range(4):
            seen[cur] = cur
            cur = rotate_cw(cur)
        cur = flip_h(cur)
    return list(seen.values())


ORIENTATIONS = {name: orientations_of(cells) for name, cells in PIECE_DEFS.items()}


def centroid_of(cells):
    """Centro aproximado: ancla el fantasma al cursor como en la version web."""
    r = round(sum(c[0] for c in cells) / len(cells))
    c = round(sum(c[1] for c in cells) / len(cells))
    return r, c


def bounds_of(cells):
    rows = max(c[0] for c in cells) + 1
    cols = max(c[1] for c in cells) + 1
    return rows, cols
