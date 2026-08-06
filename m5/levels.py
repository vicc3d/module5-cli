"""The 20 levels of Shapes mode and the classic 6x10 board.

Silhouettes identical to src/levels.js: already verified as solvable with
distinct pentominoes via an exact-cover solver.
"""

RAW_LEVELS = [
    ("Cruz", """
.X.
XXX
.X."""),
    ("Escalon", """
X..
XX.
.XX"""),
    ("Esquina", """
XX....
XX....
XXXXXX"""),
    ("Torre", """
XX.
XXX
XX.
XX.
X.."""),
    ("Bloque 3x5", """
XXXXX
XXXXX
XXXXX"""),
    ("Piramide", """
..XXX..
.XXXXX.
XXXXXXX"""),
    ("Bloque 4x5", """
XXXXX
XXXXX
XXXXX
XXXXX"""),
    ("La U", """
XX..XX
XX..XX
XXXXXX
XXXXXX"""),
    ("Cuadrado 5x5", """
XXXXX
XXXXX
XXXXX
XXXXX
XXXXX"""),
    ("Diamante", """
...X...
..XXX..
.XXXXX.
XXXXXXX
.XXXXX.
..XXX..
...X..."""),
    ("Bloque 6x5", """
XXXXX
XXXXX
XXXXX
XXXXX
XXXXX
XXXXX"""),
    ("La H", """
XX...XX
XX...XX
XXXXXXX
XXXXXXX
XX...XX
XX...XX"""),
    ("Franja 3x10", """
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX"""),
    ("Bloque 5x7", """
XXXXXXX
XXXXXXX
XXXXXXX
XXXXXXX
XXXXXXX"""),
    ("Franja 4x10", """
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX"""),
    ("Zigzag", """
XXXXX.....
XXXXX.....
XXXXXXXXXX
XXXXXXXXXX
.....XXXXX
.....XXXXX"""),
    ("Gran Cruz", """
...XXX...
...XXX...
...XXX...
XXXXXXXXX
XXXXXXXXX
XXXXXXXXX
...XXX...
...XXX...
...XXX..."""),
    ("Bloque 5x10", """
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX"""),
    ("El Nucleo", """
XXXXXXXXXX
XXXX.XXXXX
XXX...XXXX
XXXX.XXXXX
XXXXXXXXXX
XXXXXXXXXX"""),
    ("El Tablero", """
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX
XXXXXXXXXX"""),
]

# English names, in the same order (from src/i18n.js).
LEVEL_NAMES_EN = [
    "Cross", "Step", "Corner", "Tower", "Block 3x5", "Pyramid", "Block 4x5",
    "The U", "Square 5x5", "Diamond", "Block 6x5", "The H", "Strip 3x10",
    "Block 5x7", "Strip 4x10", "Zigzag", "Great Cross", "Block 5x10",
    "The Core", "The Board",
]


def parse_shape(art):
    cells = []
    for r, row in enumerate(art.strip().split("\n")):
        for c, ch in enumerate(row):
            if ch == "X":
                cells.append((r, c))
    return cells


class Board:
    """A playable board: the target silhouette and its dimensions."""

    __slots__ = ("name", "cells", "rows", "cols", "pieces", "created_at", "index")

    def __init__(self, name, cells, created_at=None, index=0):
        self.name = name
        self.cells = list(cells)
        self.rows = max(c[0] for c in self.cells) + 1
        self.cols = max(c[1] for c in self.cells) + 1
        self.pieces = len(self.cells) // 5
        self.created_at = created_at
        self.index = index


LEVELS = [
    Board(name, parse_shape(art), index=i)
    for i, (name, art) in enumerate(RAW_LEVELS)
]

# Classic 6x10 board: all 12 pieces, no gaps.
CLASSIC = Board("Clasico 6x10", [(r, c) for r in range(6) for c in range(10)])

# Known results for the 6x10 rectangle.
CLASSIC_SOLUTIONS = 2339
CLASSIC_VARIANTS = 9356
