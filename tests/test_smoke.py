"""Smoke tests: run the whole game without a real terminal.

    python3 tests/test_smoke.py

Cover the rules that matter (classic mode's unique solutions, level
unlocking, editor verification, codes compatible with the web version) and
that no screen blows up across different sizes, themes, and color modes.
"""

import sys

from harness import Harness, auto_solve

from m5 import glyphs
from m5.glyphs import g
from m5.levels import CLASSIC_SOLUTIONS, LEVELS
from m5.solver import check_solvable, solve
from m5.store import decode_challenge, encode_challenge

FAILED = []


def check(label, cond, extra=""):
    mark = "ok  " if cond else "FAIL"
    print("  [%s] %s%s" % (mark, label, (": " + extra) if extra and not cond else ""))
    if not cond:
        FAILED.append(label)


def section(name):
    print("\n== %s" % name)


# 1. Solver

def test_solver():
    section("solver")
    for lv in LEVELS:
        placements, timed_out = solve(lv.cells, time_limit=30)
        ok = placements is not None and not timed_out
        if ok:
            # the pieces must all be distinct and cover the silhouette exactly
            names = [p[0] for p in placements]
            covered = 0
            for _, mask in placements:
                covered |= mask
            ok = (len(names) == len(set(names))
                  and covered == (1 << len(lv.cells)) - 1
                  and len(names) == len(lv.cells) // 5)
        check("level %02d %s solvable" % (lv.index + 1, lv.name), ok)
    check("5 cells in a row with a gap: no solution",
          check_solvable([(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (2, 0)])[0] is False)
    check("two separate rows of 5: no solution (would need the I twice)",
          check_solvable([(0, c) for c in range(5)] + [(2, c) for c in range(5)])[0] is False)
    check("13 cells: rejected, not a multiple of 5",
          check_solvable([(0, c) for c in range(13)])[0] is False)


# 2. Challenge codes

def test_codes():
    section("challenge codes (web version format)")
    # reference values generated with encodeChallenge() from src/main.js
    cases = [
        ({"name": "Cruz Prueba", "cells": [[0, 1], [0, 2], [1, 0], [1, 1], [2, 1]],
          "rows": 3, "cols": 3},
         "M5.eyJuIjoiQ3J1eiBQcnVlYmEiLCJyIjozLCJjIjozLCJiIjoiZVFBPSJ9"),
        ({"name": "Tablero ñ", "cells": [[r, c] for r in range(6) for c in range(10)],
          "rows": 6, "cols": 10},
         "M5.eyJuIjoiVGFibGVybyDDsSIsInIiOjYsImMiOjEwLCJiIjoiLy8vLy8vLy8vL0E9In0="),
    ]
    for ch, expected in cases:
        got = encode_challenge(ch)
        check("encodes %r the same as the web" % ch["name"], got == expected, got)
        back = decode_challenge(expected)
        same = (back is not None
                and sorted(map(tuple, back["cells"])) == sorted(map(tuple, ch["cells"]))
                and back["name"] == ch["name"])
        check("decodes %r" % ch["name"], same)
    for bad in ("", "hola", "M5.", "M5.####", "M5." + "eyJ4IjoxfQ=="):
        check("rejects invalid code %r" % bad, decode_challenge(bad) is None)


# 3. Classic mode: unique solutions

def test_classic():
    section("classic mode")
    h = Harness()
    h.key("enter")
    check("enters the game", h.top == "GameScreen")
    auto_solve(h)
    check("the board is complete", h.game.is_complete())
    check("the victory modal appears", h.top == "Modal", h.top)
    check("records 1 solution", len(h.store.solutions) == 1)
    check("saves a best time", h.store.data.get("classic_best") is not None)
    canon = h.store.solutions[0]
    check("the canonical form is 60 characters", len(canon) == 60)

    # repeating the SAME solution must be rejected
    h.key("enter")  # "Buscar otra solucion" -> resets the board
    check("the board was reset", len(h.game.placed) == 0)
    auto_solve(h)
    check("second time: the repeated notice shows", h.top == "Modal")
    check("a repeated solution is not counted", len(h.store.solutions) == 1,
          str(len(h.store.solutions)))
    check("the title says repeated", h.has("REPETIDA"), h.text()[:200])

    # a solution equivalent by symmetry also counts as repeated
    h2 = Harness()
    h2.key("enter")
    auto_solve(h2)
    before = len(h2.store.solutions)
    check("another instance starts from zero", before == 1)


def test_place_and_pickup():
    section("placing and taking back with the keyboard")
    h = Harness()
    h.key("enter")
    h.keys("1")                       # F
    check("the piece is in hand", h.game.sel is not None)
    h.key("enter")                    # fits centered
    check("it is placed", len(h.game.placed) == 1 and "F" in h.game.placed)
    check("the counter goes up", h.has("1/12"), h.text())
    check("the selection is released", h.game.sel is None)

    # the vertical I centered runs off the bottom of the board: invalid ghost
    h.keys("2")
    ghost = h.game.ghost()
    check("the I ghost is marked invalid", ghost is not None and not ghost.valid)
    h.key("enter")
    check("an invalid piece is not placed", len(h.game.placed) == 1)
    # still invalid a row up: there it collides with the F just placed
    h.key("up")
    check("collides with the piece already placed", not h.game.ghost().valid)
    # it fits at column 0: cursor (2,0) anchors the I across rows 0-4
    for _ in range(5):
        h.key("left")
    check("fits in a free column", h.game.ghost().valid,
          str(h.game.ghost().cells))
    h.key("enter")
    check("the I is placed", len(h.game.placed) == 2, str(h.game.placed.keys()))

    # the cursor ended up on the I just placed: backspace takes it back
    h.key("backspace")
    check("backspace takes it back", len(h.game.placed) == 1, str(h.game.placed.keys()))
    check("and it returns to the hand", h.game.sel is not None and h.game.sel["name"] == "I")
    h.key("esc")
    check("esc cancels the selection", h.game.sel is None)
    check("esc again asks before leaving", True)
    h.key("esc")
    check("offers to save when leaving with pieces placed", h.top == "Modal", h.top)

    # a placed piece's key takes it back (like clicking it in the web version)
    h.key("esc")
    h2 = Harness()
    h2.key("enter").keys("1").key("enter")
    check("F placed", "F" in h2.game.placed)
    h2.keys("1")
    check("its key takes it back", "F" not in h2.game.placed
          and h2.game.sel and h2.game.sel["name"] == "F")

    # the mouse does the same (coordinates depend on the board's scale)
    h3 = Harness()
    h3.key("enter").keys("1")
    gs = h3.app.top
    cw, chh = gs.scale
    px = gs.board_x + 2 + 5 * cw
    py = gs.board_y + 1 + 3 * chh
    check("the click targets the expected cell", gs.cell_at(px, py) == (3, 5),
          str(gs.cell_at(px, py)))
    h3.mouse("press", "left", px, py)
    check("the click places", len(h3.game.placed) == 1, str(h3.game.placed))
    h3.mouse("press", "left", px, py)
    check("clicking the piece takes it back", len(h3.game.placed) == 0)
    check("a click outside the board does nothing", gs.cell_at(0, 0) is None)


def test_menu_layout():
    section("menu layout")
    from m5.screens import MenuScreen, menu_columns, menu_plan, menu_worst_height

    def resolved_desc_gap(items, w, hh):
        # replays MenuScreen.draw()'s own layout selection, so the test checks
        # what the code actually promises for this size, not a fixed guess
        limit = hh - 3
        ww = min(64, w - 4)
        chosen = MenuScreen.LAYOUTS[-1]
        for cand in MenuScreen.LAYOUTS:
            top = 1 + (6 if cand[0] else 2) + 2
            if top + menu_worst_height(items, ww, cand[1], cand[2], cand[3]) <= limit:
                chosen = cand
                break
        return chosen[2]

    for w, hh in ((100, 30), (80, 24), (70, 22), (60, 20), (50, 18), (46, 16)):
        for lang in ("es", "en"):
            h = Harness(w, hh, lang=lang)
            h.render()
            raw = h.lines()
            # a row counts as blank even if it carries the divider line
            blank = lambda ln: ln.replace(g("v"), " ").replace("|", " ").strip() == ""
            lines = [ln.rstrip() for ln in raw]
            title_y = next(i for i, ln in enumerate(lines) if "01" in ln)
            check("%dx%d/%s: the figure sits on the title row" % (w, hh, lang),
                  "/" in lines[title_y], lines[title_y])
            # the blank-line guarantee only holds when the chosen layout has
            # room to spare it (desc_gap >= 1); the tightest fallback drops it
            # on purpose rather than overflowing the terminal
            has_gap = resolved_desc_gap(MenuScreen(h.app).items(), w, hh) >= 1
            if has_gap:
                check("%dx%d/%s: blank line under the figure" % (w, hh, lang),
                      blank(lines[title_y + 1]), repr(lines[title_y + 1]))
            nxt = next((i for i, ln in enumerate(lines) if "02" in ln), None)
            if has_gap:
                check("%dx%d/%s: blank line above the next option" % (w, hh, lang),
                      nxt is not None and blank(lines[nxt - 1]),
                      repr(lines[nxt - 1]) if nxt else "no 02")
            check("%dx%d/%s: the menu does not overlap the footer" % (w, hh, lang),
                  nxt is None or nxt < hh - 3, "02 at %s of %d" % (nxt, hh))

            # the important part: the description doesn't invade the value column
            mw = min(64, w - 4)
            x0 = (w - mw) // 2
            div, text_w = menu_columns(MenuScreen(h.app).items(), mw)
            if div is None:
                continue
            col = x0 + div
            check("%dx%d/%s: there is a vertical line on the title row" % (w, hh, lang),
                  raw[title_y][col] in "|" + g("v"), repr(raw[title_y][col]))
            for dy in (1, 2, 3):  # the gap and the description lines
                row = raw[title_y + dy]
                check("%dx%d/%s: row +%d respects the column" % (w, hh, lang, dy),
                      row[col] in "|" + g("v") and row[:col].rstrip() == row[:col].rstrip(),
                      repr(row))
                check("%dx%d/%s: no text past the line at +%d"
                      % (w, hh, lang, dy), row[col + 1:].strip() == "",
                      repr(row[col + 1:]))

    # measuring and drawing come from the same plan: they can't get out of sync
    items = MenuScreen(Harness(80, 24).app).items()
    for gap in (0, 1):
        for dg in (0, 1):
            for md in (0, 1, 2):
                heights = [menu_plan(items, i, 60, gap, dg, md)[1]
                           for i in range(len(items))]
                rows_max = max(
                    max((y for y, _, _ in menu_plan(items, i, 60, gap, dg, md)[0]),
                        default=0) + 1
                    for i in range(len(items)))
                check("plan gap=%d desc_gap=%d max_desc=%d: the height covers the rows"
                      % (gap, dg, md), max(heights) >= rows_max,
                      "alto %d filas %d" % (max(heights), rows_max))
                check("plan gap=%d desc_gap=%d max_desc=%d: the worst case is the maximum"
                      % (gap, dg, md),
                      menu_worst_height(items, 60, gap, dg, md) == max(heights))


def test_board_scaling():
    section("board scale")
    from m5.screens import EditorScreen
    from m5.ui import CELL_SCALES, board_size
    from m5.levels import CLASSIC

    h = Harness(100, 30)
    h.key("enter")
    gs = h.app.top
    check("at 100x30 classic uses 4x2 cells", gs.scale == (4, 2), str(gs.scale))
    w, _ = board_size(CLASSIC, gs.scale)
    check("the board is more than twice the minimum width",
          w >= 2 * board_size(CLASSIC)[0] - 3, str(w))

    # a small silhouette gets enlarged more so it doesn't get lost
    h2 = Harness(100, 30)
    h2.game.start_level(0)
    h2.app.stack = [h2.app.stack[0]]
    h2.key("down").key("enter").key("enter")
    check("level 1 (5 cells) uses large cells",
          h2.app.top.scale[0] >= 6, str(h2.app.top.scale))

    # manual zoom with + / _ (shift-= and shift-- on a US keyboard)
    h4 = Harness(100, 30)
    h4.key("enter")
    gs = h4.app.top
    auto = gs.scale
    h4.type("+")
    check("+ zooms in", gs.scale[0] > auto[0], "%s -> %s" % (auto, gs.scale))
    check("the zoom is stored", h4.app.zoom is not None)
    zoomed = gs.scale
    for _ in range(4):
        h4.type("+")
    check("+ does not exceed what fits on screen", gs.scale == zoomed, str(gs.scale))
    h4.type("_")
    check("_ zooms out", gs.scale == auto, str(gs.scale))
    check("returning to the automatic scale clears the zoom", h4.app.zoom is None)
    for _ in range(4):
        h4.type("_")
    check("_ does not go below the minimum scale", gs.scale == (2, 1), str(gs.scale))

    # the piece keys -/= must not get confused with zoom
    h4.type("-")
    check("- still picks piece Y",
          h4.game.sel is not None and h4.game.sel["name"] == "Y")
    h4.type("=")
    check("= still picks piece Z",
          h4.game.sel is not None and h4.game.sel["name"] == "Z")

    # the mouse wheel also zooms, like the web's ASCII view
    h5 = Harness(100, 30)
    h5.key("enter")
    gs = h5.app.top
    small = gs.scale
    h5.mouse("wheel", "up", 50, 15)
    check("the wheel zooms in", gs.scale[0] > small[0], str(gs.scale))
    h5.mouse("wheel", "down", 50, 15)
    check("the wheel zooms out", gs.scale == small, str(gs.scale))

    # zoom survives a restart and clamps if it no longer fits
    h6 = Harness(100, 30)
    h6.key("enter")
    h6.type("+")
    h7 = Harness(100, 30, home=h6.tmp)
    h7.key("enter")
    check("the zoom survives a restart", h7.app.top.scale == h6.app.top.scale,
          str(h7.app.top.scale))
    h8 = Harness(60, 20, settings={"zoom": 3})
    h8.key("enter")
    gs = h8.app.top
    bw, bh = board_size(h8.game.board, gs.scale)
    check("a stored zoom that does not fit is clamped",
          gs.board_x + bw <= 60 and gs.board_y + bh <= 18, str(gs.scale))
    for junk in ("abc", -5, 99, [1], {}):
        hx = Harness(100, 30, settings={"zoom": junk})
        hx.key("enter")
        check("invalid zoom %r breaks nothing" % (junk,),
              hx.app.top.scale in CELL_SCALES, str(hx.app.top.scale))

    # the editor shares the same zoom
    h9 = Harness(100, 30)
    h9.app.push(EditorScreen(h9.app))
    h9.render()
    ed = h9.app.top
    ed_auto = ed.scale
    h9.type("+")
    check("the editor zooms too", ed.scale[0] > ed_auto[0], str(ed.scale))
    cw, chh = ed.scale
    h9.mouse("press", "left", ed.gx + 2 + 3 * cw, ed.gy + 1 + 2 * chh)
    check("and the click paints the right cell at the new scale", (2, 3) in ed.cells,
          str(sorted(ed.cells)))

    # and on a small terminal it falls back to the minimum scale without overflowing
    for w, hh in ((46, 16), (60, 20), (80, 24), (100, 30), (140, 45)):
        h3 = Harness(w, hh)
        h3.key("enter")
        gs = h3.app.top
        bw, bh = board_size(h3.game.board, gs.scale)
        fits = (gs.board_x + bw <= w) and (gs.board_y + bh <= hh - 2)
        check("at %dx%d the board fits (scale %s)" % (w, hh, gs.scale), fits,
              "x=%d w=%d y=%d h=%d" % (gs.board_x, bw, gs.board_y, bh))


def test_canonical_symmetry():
    section("canonicalization (180 rotation and mirrors)")
    from m5.game import Game
    from m5.levels import CLASSIC
    gm = Game()
    gm.start_classic()
    placements, _ = solve(CLASSIC.cells, time_limit=30)
    cell_list = [tuple(c) for c in CLASSIC.cells]
    grid = {}
    for name, mask in placements:
        for i in range(len(cell_list)):
            if (mask >> i) & 1:
                grid[cell_list[i]] = name
    gm.occupied = dict(grid)
    base = gm.canonical_solution()
    # horizontal mirror of the board -> same canonical form
    gm.occupied = {(r, 9 - c): n for (r, c), n in grid.items()}
    check("horizontal mirror gives the same canonical form", gm.canonical_solution() == base)
    gm.occupied = {(5 - r, c): n for (r, c), n in grid.items()}
    check("vertical mirror gives the same canonical form", gm.canonical_solution() == base)
    gm.occupied = {(5 - r, 9 - c): n for (r, c), n in grid.items()}
    check("180 rotation gives the same canonical form", gm.canonical_solution() == base)


# 4. Levels: unlocking

def test_levels():
    section("shapes mode")
    h = Harness()
    h.key("down").key("enter")
    check("opens the level list", h.top == "LevelsScreen")
    check("level 2 starts locked", h.has("02 ?????"))
    h.key("enter")
    check("enters level 1", h.top == "GameScreen")
    auto_solve(h)
    check("level 1 completed", h.top == "Modal" and h.has("NIVEL 1 COMPLETADO"))
    check("saves the best time for level 1", h.store.level_best(0) is not None)
    check("announces the unlock", h.has("Desbloqueaste el nivel 2"))
    h.key("enter")  # "Nivel 2"
    check("starts level 2", h.top == "GameScreen" and h.game.level_index == 1)


# 5. Editor and verification

def test_editor():
    section("challenge editor")
    h = Harness()
    h.key("down").key("down").key("enter")   # Mis desafios
    check("opens my challenges", h.top == "CustomsScreen")
    h.keys("n")
    check("opens the editor", h.top == "EditorScreen")
    ed = h.app.top

    # a cross (the X pentomino): solvable with one piece
    for cell in [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)]:
        ed.cells.add(cell)
    ed.invalidate()
    h.keys("v")
    check("verifies a cross as solvable", ed.verified == ed.key(), ed.status)
    check("says so on screen", h.has("RESOLUBLE"), ed.status)

    # an impossible silhouette: 5 cells in an L with a loose gap
    ed.cells.clear()
    for cell in [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4)]:
        ed.cells.add(cell)
    ed.invalidate()
    h.keys("v")
    check("detects the unsolvable silhouette", ed.verified is None, ed.status)
    check("says so on screen", h.has("SIN SOLUCION"), ed.status)

    # saving requires prior verification
    h.keys("s")
    check("does not save without verifying", len(h.store.custom) == 0)

    ed.cells.clear()
    for cell in [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)]:
        ed.cells.add(cell)
    ed.invalidate()
    h.keys("v").keys("s")
    check("asks for the name", h.top == "PromptScreen", h.top)
    h.type("Mi Cruz").key("enter")
    check("saves the challenge", len(h.store.custom) == 1,
          str(h.store.custom))
    check("saves with the typed name",
          h.store.custom and h.store.custom[0]["name"] == "Mi Cruz")
    check("returns to my challenges", h.top == "CustomsScreen", h.top)

    # play it start to finish
    h.key("enter")
    check("plays the own challenge", h.top == "GameScreen")
    auto_solve(h)
    check("completes the own challenge",
          h.top == "Modal" and h.has("DESAFIO COMPLETADO"), h.top)
    check("saves the challenge record", h.store.custom[0]["best"] is not None)


def test_import():
    section("importing a code")
    h = Harness()
    h.key("down").key("down").key("enter").keys("i")
    check("opens the import screen", h.top == "ImportScreen")
    h.paste("M5.eyJuIjoiQ3J1eiBQcnVlYmEiLCJyIjozLCJjIjozLCJiIjoiZVFBPSJ9")
    h.key("enter")
    check("imports the challenge", len(h.store.custom) == 1, h.text()[-300:])
    check("with its name", h.store.custom[0]["name"] == "Cruz Prueba")

    h2 = Harness()
    h2.key("down").key("down").key("enter").keys("i")
    h2.type("basura").key("enter")
    check("rejects an invalid code", len(h2.store.custom) == 0)
    check("and warns", h2.has("invalido"), h2.text()[-300:])


# 6. Saved games

def test_slots():
    section("saved games")
    import time as _time
    h = Harness()
    h.key("enter")            # classic
    h.keys("1").key("enter")  # places the F
    placed_before = dict(h.game.placed)
    check("one piece is placed", len(placed_before) == 1)
    _time.sleep(0.02)         # give the clock something to save
    h.app.save_slot(0)
    check("slot 0 is taken", bool(h.store.slots.get("0")))
    h.app.go_menu()
    check("back at the menu", h.top == "MenuScreen")
    h.app.load_slot(0)
    check("reloads the game", h.top == "GameScreen")
    check("with the piece placed", len(h.game.placed) == 1)
    check("and the clock running", h.game.start_time is not None)

    # a corrupted snapshot shouldn't break anything
    h.store.slots["1"] = {"mode": "level", "level_index": 999, "placed": []}
    h.app.load_slot(1)
    check("ignores an invalid slot", h.top == "GameScreen")
    h.store.slots["2"] = {"mode": "classic", "elapsed": 0,
                          "placed": [{"name": "ZZ", "orient": [[0, 0]],
                                      "anchor_r": 0, "anchor_c": 0}]}
    h.app.load_slot(2)
    check("ignores a nonexistent piece in a slot", h.top == "GameScreen")

    # a save file whose settings aren't an object must not crash startup
    import json
    import os
    import tempfile
    home = tempfile.mkdtemp(prefix="module5-test-")
    with open(os.path.join(home, "save.json"), "w", encoding="utf-8") as fh:
        json.dump({"settings": ["x"], "solutions": ["keep"]}, fh)
    try:
        h3 = Harness(home=home)
        ok = h3.store.settings["mouse"] is True and h3.store.solutions == ["keep"]
    except Exception:  # noqa: BLE001
        ok = False
    check("malformed settings in the save file fall back to defaults", ok)


def test_about():
    section("about")
    from m5 import __version__

    for lang in ("es", "en"):
        h = Harness(100, 30, lang=lang)
        h.key("down").key("down").key("down").key("down").key("enter")  # menu -> Settings
        items = h.app.top.items()
        check("%s: there is an 'about' row" % lang,
              any(it["key"] == "about" for it in items))
        idx = next(i for i, it in enumerate(items) if it["key"] == "about")
        for _ in range(idx):
            h.key("down")
        h.key("enter")
        check("%s: opens a modal" % lang, h.top == "Modal")
        check("%s: shows the version" % lang, h.has(__version__), h.text())
        check("%s: mentions the license" % lang, h.has("MIT License"), h.text())
        check("%s: credits the author" % lang, h.has("Victor Crespo"), h.text())
        h.key("enter")  # Close
        check("%s: returns to Settings" % lang, h.top == "SettingsScreen")


def test_saved_games_menu_item():
    section("saved games as a main-menu item")
    from m5.screens import MenuScreen, SettingsScreen, SlotsScreen

    h = Harness()
    menu_items = MenuScreen(h.app).items()
    check("there is a 'slots' row in the main menu",
          any(it["key"] == "slots" for it in menu_items))
    settings_items = SettingsScreen(h.app).items()
    check("it is no longer duplicated inside Settings",
          not any(it["key"] == "slots" for it in settings_items))

    idx = next(i for i, it in enumerate(menu_items) if it["key"] == "slots")
    for _ in range(idx):
        h.key("down")
    h.key("enter")
    check("opens Saved games from the menu", h.top == "SlotsScreen")
    h.key("esc")
    check("returns to the menu", h.top == "MenuScreen")


def test_settings_from_game():
    section("settings reachable mid-game")
    h = Harness()
    h.key("enter")  # Classic
    check("enters the game", h.top == "GameScreen")
    h.keys("1")      # select the F, to confirm it is still in hand on return
    h.keys("o")
    check("'o' opens Settings without going through the menu", h.top == "SettingsScreen")

    # a theme change made here must show when back in the game
    before = h.app.store.settings.get("theme", "neon")
    h.app.top.activate("theme", 1)
    after = h.app.store.settings.get("theme", "neon")
    check("the theme changed", after != before, "%s -> %s" % (before, after))

    h.key("esc")
    check("esc returns to the game (not the main menu)", h.top == "GameScreen")
    check("the selected piece was kept", h.game.sel is not None
          and h.game.sel["name"] == "F")
    check("the board already shows the new theme", h.app.theme.key == after)


def test_classic_shows_preview():
    section("target preview in classic too")
    # the web draws #preview (a minimap that fills in with color) in ALL
    # modes, classic included; the original port left it out there by mistake
    h = Harness()
    h.key("enter")
    gs = h.app.top
    sil_h, _ = gs.panel_body()
    check("classic reserves height for the target", sil_h > 0, sil_h)

    h.keys("1").key("enter")  # places the F
    scr = h.term.screen
    accent = h.app.theme.accent
    dim = h.app.theme.text_dim
    # inside the panel rectangle (columns ~76-95) there must be cells in the
    # accent color (placed pieces) and cells in the dim color (target still
    # empty). If both appear, the minimap shows real progress, not a
    # uniform block
    seen = {row[x][1] for y, row in enumerate(scr.buf) for x in range(76, 96)}
    check("there are cells in the accent color (filled)", accent in seen)
    check("there are cells in the dim color (empty)", dim in seen)


# 7. Drawing robustness

def walk_all_screens(h):
    """Walks through every screen and draws it."""
    from m5.screens import (CustomsScreen, EditorScreen, GameScreen, HelpScreen,
                            ImportScreen, LevelsScreen, MenuScreen, SettingsScreen,
                            SlotsScreen)
    app = h.app
    app.game.start_classic()
    for cls in (MenuScreen, LevelsScreen, CustomsScreen, SettingsScreen,
                SlotsScreen, EditorScreen, GameScreen, HelpScreen, ImportScreen):
        app.stack = [MenuScreen(app), cls(app)]
        h.render()
    # with a piece in hand and a modal on top
    app.stack = [MenuScreen(app), GameScreen(app)]
    app.game.select("I")
    h.render()
    app.confirm_leave()
    h.render()
    app.game.start_level(9)   # Diamond, 7x7
    app.stack = [MenuScreen(app), GameScreen(app)]
    h.render()
    app.game.start_level(16)  # Great Cross, 9x9
    h.render()


def test_render_matrix():
    section("drawing across sizes, themes, and color modes")
    sizes = [(46, 16), (60, 20), (80, 24), (100, 30), (120, 40), (200, 50),
             (30, 10), (20, 8), (46, 15)]
    for theme in ("neon", "ascii", "blueprint", "mono"):
        for color in ("truecolor", "256", "16", "mono"):
            for ascii_mode in (False, True):
                glyphs.use_ascii(ascii_mode)
                try:
                    h = Harness(100, 30, color_mode=color, theme=theme)
                    for w, hh in sizes:
                        h.term.resize(w, hh)
                        h.term.sync_size()
                        walk_all_screens(h)
                except Exception as exc:  # noqa: BLE001
                    import traceback
                    traceback.print_exc()
                    check("theme=%s color=%s ascii=%s" % (theme, color, ascii_mode),
                          False, repr(exc))
                    return
    check("every theme/color/glyph/size combination draws", True)
    glyphs.use_ascii(False)


def test_no_crash_on_random_input():
    section("arbitrary input")
    import random
    random.seed(7)
    names = ["up", "down", "left", "right", "enter", "space", "esc", "tab",
             "backspace", "delete", "home", "end", "shift-tab", "pgup", "pgdn"]
    chars = list("123456789 0-=rfxcnsivqd?ABZ")
    h = Harness(90, 28)
    from m5.term import Key, Mouse
    for i in range(4000):
        roll = random.random()
        if roll < 0.55:
            ev = Key(random.choice(names))
        elif roll < 0.9:
            ev = Key("char", random.choice(chars))
        else:
            ev = Mouse(random.choice(["press", "drag", "release"]),
                       random.choice(["left", "right"]),
                       random.randrange(0, 90), random.randrange(0, 28))
        try:
            h.app.dispatch(ev)
            h.render()
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("event %d (%r) does not break" % (i, ev), False, repr(exc))
            return
        if not h.app.running:       # it may have chosen to quit
            h.app.running = True
    check("4000 random events without exceptions", True)


def main():
    test_solver()
    test_codes()
    test_classic()
    test_place_and_pickup()
    test_menu_layout()
    test_board_scaling()
    test_canonical_symmetry()
    test_levels()
    test_editor()
    test_import()
    test_slots()
    test_about()
    test_saved_games_menu_item()
    test_settings_from_game()
    test_classic_shows_preview()
    test_render_matrix()
    test_no_crash_on_random_input()
    print()
    if FAILED:
        print("%d checks FAILED:" % len(FAILED))
        for name in FAILED:
            print("  - " + name)
        return 1
    print("all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
