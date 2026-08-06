"""Estado del juego: tablero, piezas colocadas, fantasma, reloj y victoria.

Es el equivalente del bloque de estado de src/main.js, sin nada de dibujo: se
puede instanciar y jugar entero sin terminal (asi estan escritas las pruebas).
La diferencia de interaccion con la web es que aca el mouse se reemplaza por un
cursor que se mueve con el teclado; el fantasma sigue anclandose por el
centroide de la orientacion, igual que alli.
"""

import time

from .levels import CLASSIC, LEVELS, Board
from .pieces import (
    PIECE_DEFS,
    centroid_of,
    flip_h,
    normalize_cells,
    rotate_cw,
)


class Ghost:
    __slots__ = ("anchor_r", "anchor_c", "cells", "valid")

    def __init__(self, anchor_r, anchor_c, cells, valid):
        self.anchor_r = anchor_r
        self.anchor_c = anchor_c
        self.cells = cells
        self.valid = valid


class Game:
    """Una partida en curso (o ninguna, si mode es None)."""

    def __init__(self):
        self.mode = None          # 'classic' | 'level' | 'custom'
        self.level_index = 0
        self.board = None
        self.target = set()
        self.placed = {}          # nombre -> {'orient', 'anchor_r', 'anchor_c', 'cells'}
        self.occupied = {}        # (r, c) -> nombre
        self.sel = None           # {'name', 'orient'}
        self.cursor = (0, 0)
        self.start_time = None    # monotonic, en segundos
        self.end_time = None
        self.current_slot = None

    # --- arranque ----------------------------------------------------------

    def start(self, mode, board, level_index=0):
        self.mode = mode
        self.board = board
        self.level_index = level_index
        self.current_slot = None
        self.target = {tuple(c) for c in board.cells}
        self.placed = {}
        self.occupied = {}
        self.sel = None
        self.start_time = None
        self.end_time = None
        self.cursor = self._initial_cursor()

    def start_classic(self):
        self.start("classic", CLASSIC)

    def start_level(self, i):
        self.start("level", LEVELS[i], level_index=i)

    def start_custom(self, ch):
        board = Board(ch["name"], [tuple(c) for c in ch["cells"]],
                      created_at=ch.get("created_at"))
        self.start("custom", board)

    def _initial_cursor(self):
        """Arranca en la celda valida mas cercana al centro del tablero."""
        cr, cc = self.board.rows // 2, self.board.cols // 2
        if (cr, cc) in self.target:
            return (cr, cc)
        return min(self.target, key=lambda p: abs(p[0] - cr) + abs(p[1] - cc))

    def reset_board(self):
        self.placed = {}
        self.occupied = {}
        self.sel = None
        self.start_time = None
        self.end_time = None

    # --- reloj -------------------------------------------------------------

    def elapsed(self):
        """Segundos jugados (0 hasta colocar la primera pieza)."""
        if self.start_time is None:
            return 0.0
        return (self.end_time or time.monotonic()) - self.start_time

    def elapsed_ms(self):
        return int(self.elapsed() * 1000)

    # --- seleccion y fantasma ---------------------------------------------

    def select(self, name):
        if name in self.placed or name not in PIECE_DEFS:
            return False
        self.sel = {"name": name, "orient": normalize_cells(PIECE_DEFS[name])}
        return True

    def deselect(self):
        self.sel = None

    def cycle_selection(self, step):
        """Pasa a la siguiente pieza disponible (TAB)."""
        from .pieces import PIECE_NAMES
        free = [n for n in PIECE_NAMES if n not in self.placed]
        if not free:
            return
        if self.sel is None:
            self.select(free[0] if step > 0 else free[-1])
            return
        try:
            i = free.index(self.sel["name"])
        except ValueError:
            self.select(free[0])
            return
        self.select(free[(i + step) % len(free)])

    def rotate(self):
        if self.sel:
            self.sel["orient"] = rotate_cw(self.sel["orient"])

    def flip(self):
        if self.sel:
            self.sel["orient"] = flip_h(self.sel["orient"])

    def ghost_at(self, r, c):
        """El fantasma centrado en (r, c), como en la version web."""
        if not self.sel:
            return None
        cr, cc = centroid_of(self.sel["orient"])
        anchor_r, anchor_c = r - cr, c - cc
        cells = [(rr + anchor_r, cc2 + anchor_c) for rr, cc2 in self.sel["orient"]]
        valid = all(cell in self.target and cell not in self.occupied for cell in cells)
        return Ghost(anchor_r, anchor_c, cells, valid)

    def ghost(self):
        return self.ghost_at(*self.cursor)

    def move_cursor(self, dr, dc):
        r = min(max(self.cursor[0] + dr, 0), self.board.rows - 1)
        c = min(max(self.cursor[1] + dc, 0), self.board.cols - 1)
        self.cursor = (r, c)

    def set_cursor(self, r, c):
        if 0 <= r < self.board.rows and 0 <= c < self.board.cols:
            self.cursor = (r, c)
            return True
        return False

    # --- colocar y retirar -------------------------------------------------

    def place(self):
        """Coloca la pieza seleccionada. Devuelve True si entro."""
        g = self.ghost()
        if not g or not g.valid:
            return False
        name = self.sel["name"]
        self.placed[name] = {
            "orient": self.sel["orient"],
            "anchor_r": g.anchor_r,
            "anchor_c": g.anchor_c,
            "cells": g.cells,
        }
        for cell in g.cells:
            self.occupied[cell] = name
        if self.start_time is None:
            self.start_time = time.monotonic()
        self.deselect()
        if self.is_complete():
            self.end_time = time.monotonic()
        return True

    def pickup(self, name):
        """Retira una pieza colocada y la deja seleccionada (como en la web)."""
        p = self.placed.pop(name, None)
        if not p:
            return False
        for cell in p["cells"]:
            self.occupied.pop(cell, None)
        self.sel = {"name": name, "orient": p["orient"]}
        self.end_time = None
        return True

    def pickup_at_cursor(self):
        name = self.occupied.get(self.cursor)
        return self.pickup(name) if name else False

    def is_complete(self):
        return len(self.occupied) == len(self.target) and bool(self.target)

    # --- solucion canonica (solo clasico) ---------------------------------

    def canonical_solution(self):
        """Forma canonica invariante a rotacion de 180 y espejos del tablero.

        Identica a canonicalSolution() de la web, para que la cuenta de
        soluciones unicas signifique lo mismo en las dos versiones.
        """
        g = [self.occupied.get((r, c), ".") for r in range(6) for c in range(10)]
        idx = lambda r, c: r * 10 + c
        variants = [
            "".join(g),
            "".join(reversed(g)),                                              # 180
            "".join(g[idx(5 - i // 10, i % 10)] for i in range(60)),           # espejo vertical
            "".join(g[idx(i // 10, 9 - (i % 10))] for i in range(60)),         # espejo horizontal
        ]
        return min(variants)

    # --- partidas guardadas ------------------------------------------------

    def snapshot(self):
        if self.mode is None:
            return None
        snap = {
            "mode": self.mode,
            "level_index": self.level_index,
            "elapsed": self.elapsed_ms(),
            "placed": [
                {
                    "name": name,
                    "orient": [list(c) for c in p["orient"]],
                    "anchor_r": p["anchor_r"],
                    "anchor_c": p["anchor_c"],
                }
                for name, p in self.placed.items()
            ],
        }
        if self.mode == "custom":
            snap["board"] = {
                "name": self.board.name,
                "cells": [list(c) for c in self.board.cells],
                "rows": self.board.rows,
                "cols": self.board.cols,
                "created_at": self.board.created_at,
            }
        return snap

    def restore(self, snap):
        """Rehidrata una partida guardada. False si el snapshot no sirve."""
        try:
            mode = snap["mode"]
            if mode == "classic":
                self.start_classic()
            elif mode == "custom":
                self.start_custom(snap["board"])
            else:
                i = int(snap.get("level_index", 0))
                if not 0 <= i < len(LEVELS):
                    return False
                self.start_level(i)
            for p in snap.get("placed", []):
                name = p["name"]
                orient = tuple(tuple(c) for c in p["orient"])
                ar, ac = p["anchor_r"], p["anchor_c"]
                cells = [(r + ar, c + ac) for r, c in orient]
                # un save manipulado (o de otra version del tablero) no debe
                # dejar el juego en un estado imposible de terminar
                if name not in PIECE_DEFS or name in self.placed:
                    return False
                if any(c not in self.target or c in self.occupied for c in cells):
                    return False
                self.placed[name] = {"orient": orient, "anchor_r": ar,
                                     "anchor_c": ac, "cells": cells}
                for cell in cells:
                    self.occupied[cell] = name
            ms = int(snap.get("elapsed", 0))
            self.start_time = time.monotonic() - ms / 1000 if ms > 0 else None
            self.end_time = None
            self.cursor = self._initial_cursor()
            return True
        except (KeyError, TypeError, ValueError):
            return False


def fmt_time(seconds):
    """mm:ss.d — el mismo formato que fmtTime() en la web."""
    if seconds is None:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds % 60
    return "%02d:%02d.%d" % (m, int(s), int((s % 1) * 10))


def fmt_ms(ms):
    return fmt_time(None if ms is None else ms / 1000)
