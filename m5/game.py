"""Game state: board, placed pieces, ghost piece, clock, and victory.

The equivalent of the state block in src/main.js, with none of the drawing:
it can be instantiated and played through entirely without a terminal (that's
how the tests are written). The interaction difference from the web is that
here the mouse is replaced by a cursor that moves with the keyboard; the
ghost piece still anchors by the orientation's centroid, same as there.
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
    """A game in progress (or none, if mode is None)."""

    def __init__(self):
        self.mode = None          # 'classic' | 'level' | 'custom'
        self.level_index = 0
        self.board = None
        self.target = set()
        self.placed = {}          # name -> {'orient', 'anchor_r', 'anchor_c', 'cells'}
        self.occupied = {}        # (r, c) -> name
        self.sel = None           # {'name', 'orient'}
        self.cursor = (0, 0)
        self.start_time = None    # monotonic, in seconds
        self.end_time = None
        self.current_slot = None

    # --- startup -------------------------------------------------------------

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
        """Starts on the valid cell closest to the center of the board."""
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

    # --- clock -----------------------------------------------------------

    def elapsed(self):
        """Seconds played (0 until the first piece is placed)."""
        if self.start_time is None:
            return 0.0
        return (self.end_time or time.monotonic()) - self.start_time

    def elapsed_ms(self):
        return int(self.elapsed() * 1000)

    # --- selection and ghost piece ------------------------------------------

    def select(self, name):
        if name in self.placed or name not in PIECE_DEFS:
            return False
        self.sel = {"name": name, "orient": normalize_cells(PIECE_DEFS[name])}
        return True

    def deselect(self):
        self.sel = None

    def cycle_selection(self, step):
        """Moves to the next available piece (TAB)."""
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
        """The ghost piece centered on (r, c), like the web version."""
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

    # --- placing and taking back ---------------------------------------------

    def place(self):
        """Places the selected piece. Returns True if it fit."""
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
        """Takes back a placed piece and leaves it selected (like the web)."""
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

    # --- canonical solution (classic only) -----------------------------------

    def canonical_solution(self):
        """Canonical form invariant to 180-degree rotation and board mirrors.

        Identical to the web's canonicalSolution(), so the count of unique
        solutions means the same thing in both versions.
        """
        g = [self.occupied.get((r, c), ".") for r in range(6) for c in range(10)]
        idx = lambda r, c: r * 10 + c
        variants = [
            "".join(g),
            "".join(reversed(g)),                                              # 180
            "".join(g[idx(5 - i // 10, i % 10)] for i in range(60)),           # vertical mirror
            "".join(g[idx(i // 10, 9 - (i % 10))] for i in range(60)),         # horizontal mirror
        ]
        return min(variants)

    # --- saved games -----------------------------------------------------

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
        """Rehydrates a saved game. False if the snapshot is invalid."""
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
                # a tampered save (or one from a different board version)
                # shouldn't leave the game in an impossible-to-finish state
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
    """mm:ss.d — the same format as fmtTime() in the web version."""
    if seconds is None:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds % 60
    return "%02d:%02d.%d" % (m, int(s), int((s % 1) * 10))


def fmt_ms(ms):
    return fmt_time(None if ms is None else ms / 1000)
