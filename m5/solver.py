"""Exact-cover solver for distinct pentominoes (each piece at most once).
Verifies that user-created challenges have a solution.

The web version ran this in a Web Worker; here there's no thread worth using
(the GIL would leave the UI frozen anyway), so it's a bitmask solver,
considerably faster than a literal port of the JS one, with an `on_tick`
callback that hands control back to the render loop every so often, to draw
the spinner and allow canceling.
"""

import time

from .pieces import ORIENTATIONS, PIECE_NAMES, bounds_of


class Cancelled(Exception):
    """The user aborted verification."""


def _popcount(x):
    return bin(x).count("1")


def _build(cell_list):
    """Precomputes, for each cell, the placements that cover it.

    Returns (covers, neighbours): `covers[i]` is the list of (piece_bit, mask)
    for every legal placement that occupies cell `i`, and `neighbours[i]` is
    the mask of orthogonally adjacent cells within the silhouette.
    """
    n = len(cell_list)
    idx = {cell: i for i, cell in enumerate(cell_list)}
    rows, cols = bounds_of(cell_list)

    covers = [[] for _ in range(n)]
    for pi, name in enumerate(PIECE_NAMES):
        piece_bit = 1 << pi
        for ori in ORIENTATIONS[name]:
            o_rows, o_cols = bounds_of(ori)
            for dr in range(rows - o_rows + 1):
                for dc in range(cols - o_cols + 1):
                    mask = 0
                    for r, c in ori:
                        i = idx.get((r + dr, c + dc))
                        if i is None:
                            mask = -1
                            break
                        mask |= 1 << i
                    if mask <= 0:
                        continue
                    placement = (piece_bit, mask)
                    m = mask
                    while m:
                        low = m & -m
                        covers[low.bit_length() - 1].append(placement)
                        m ^= low

    neighbours = [0] * n
    for i, (r, c) in enumerate(cell_list):
        m = 0
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            j = idx.get((r + dr, c + dc))
            if j is not None:
                m |= 1 << j
        neighbours[i] = m
    return covers, neighbours


def _regions_ok(free, neighbours):
    """Pruning: every connected region of free cells must be a multiple of 5."""
    while free:
        low = free & -free
        region = low
        frontier = low
        while frontier:
            nxt = 0
            f = frontier
            while f:
                b = f & -f
                nxt |= neighbours[b.bit_length() - 1]
                f ^= b
            frontier = nxt & free & ~region
            region |= frontier
        if _popcount(region) % 5:
            return False
        free &= ~region
    return True


def solve(cell_list, time_limit=10.0, on_tick=None, tick_every=20000):
    """Searches for a solution. Returns (placements | None, timed_out).

    `placements` is a list of (name, mask). `on_tick(nodes)` is called every
    `tick_every` nodes and may raise Cancelled to abort.
    """
    cell_list = list(cell_list)
    n = len(cell_list)
    if n == 0 or n % 5 or n > 60:
        return None, False

    covers, neighbours = _build(cell_list)
    full = (1 << n) - 1
    deadline = time.monotonic() + time_limit
    chosen = []
    state = {"nodes": 0, "timed_out": False}

    def rec(filled, used):
        state["nodes"] += 1
        if state["nodes"] % tick_every == 0:
            if time.monotonic() > deadline:
                state["timed_out"] = True
                return False
            if on_tick:
                on_tick(state["nodes"])
        if filled == full:
            return True
        free = full & ~filled
        if not _regions_ok(free, neighbours):
            return False
        first = (free & -free).bit_length() - 1
        for piece_bit, mask in covers[first]:
            if used & piece_bit or filled & mask:
                continue
            chosen.append((piece_bit, mask))
            if rec(filled | mask, used | piece_bit):
                return True
            chosen.pop()
            if state["timed_out"]:
                return False
        return False

    ok = rec(0, 0)
    if not ok:
        return None, state["timed_out"]
    return [(PIECE_NAMES[b.bit_length() - 1], m) for b, m in chosen], False


def check_solvable(cell_list, time_limit=10.0, on_tick=None):
    """Same as solve() but with just the verdict: (solvable, timed_out)."""
    placements, timed_out = solve(cell_list, time_limit, on_tick)
    return placements is not None, timed_out
