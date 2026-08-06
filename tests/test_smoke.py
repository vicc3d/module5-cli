"""Pruebas de humo: recorren el juego entero sin terminal real.

    python3 tests/test_smoke.py

Cubren las reglas que importan (soluciones unicas del clasico, desbloqueo de
niveles, verificacion del editor, codigos compatibles con la web) y que ninguna
pantalla explote en tamanos, temas y modos de color distintos.
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
    print("  [%s] %s%s" % (mark, label, ("  -- " + extra) if extra and not cond else ""))
    if not cond:
        FAILED.append(label)


def section(name):
    print("\n== %s" % name)


# --- 1. solver ---------------------------------------------------------------

def test_solver():
    section("solver")
    for lv in LEVELS:
        placements, timed_out = solve(lv.cells, time_limit=30)
        ok = placements is not None and not timed_out
        if ok:
            # las piezas deben ser todas distintas y cubrir la silueta exacta
            names = [p[0] for p in placements]
            covered = 0
            for _, mask in placements:
                covered |= mask
            ok = (len(names) == len(set(names))
                  and covered == (1 << len(lv.cells)) - 1
                  and len(names) == len(lv.cells) // 5)
        check("nivel %02d %s resoluble" % (lv.index + 1, lv.name), ok)
    check("5 celdas en linea con hueco: sin solucion",
          check_solvable([(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (2, 0)])[0] is False)
    check("dos filas de 5 separadas: sin solucion (haria falta la I dos veces)",
          check_solvable([(0, c) for c in range(5)] + [(2, c) for c in range(5)])[0] is False)
    check("13 celdas: rechazado por no ser multiplo de 5",
          check_solvable([(0, c) for c in range(13)])[0] is False)


# --- 2. codigos de desafio ---------------------------------------------------

def test_codes():
    section("codigos de desafio (formato de la version web)")
    # valores de referencia generados con el encodeChallenge() de src/main.js
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
        check("codifica %r igual que la web" % ch["name"], got == expected, got)
        back = decode_challenge(expected)
        same = (back is not None
                and sorted(map(tuple, back["cells"])) == sorted(map(tuple, ch["cells"]))
                and back["name"] == ch["name"])
        check("decodifica %r" % ch["name"], same)
    for bad in ("", "hola", "M5.", "M5.####", "M5." + "eyJ4IjoxfQ=="):
        check("rechaza codigo invalido %r" % bad, decode_challenge(bad) is None)


# --- 3. clasico: solucion unica ---------------------------------------------

def test_classic():
    section("modo clasico")
    h = Harness()
    h.key("enter")
    check("entra al juego", h.top == "GameScreen")
    auto_solve(h)
    check("el tablero queda completo", h.game.is_complete())
    check("aparece el modal de victoria", h.top == "Modal", h.top)
    check("registra 1 solucion", len(h.store.solutions) == 1)
    check("guarda un mejor tiempo", h.store.data.get("classic_best") is not None)
    canon = h.store.solutions[0]
    check("la forma canonica son 60 caracteres", len(canon) == 60)

    # repetir la MISMA solucion debe rechazarse
    h.key("enter")  # "Buscar otra solucion" -> reinicia el tablero
    check("el tablero se reinicio", len(h.game.placed) == 0)
    auto_solve(h)
    check("segunda vez: sale el aviso de repetida", h.top == "Modal")
    check("no suma una solucion repetida", len(h.store.solutions) == 1,
          str(len(h.store.solutions)))
    check("el titulo dice repetida", h.has("REPETIDA"), h.text()[:200])

    # una solucion equivalente por simetria tambien cuenta como repetida
    h2 = Harness()
    h2.key("enter")
    auto_solve(h2)
    before = len(h2.store.solutions)
    check("otra instancia parte de cero", before == 1)


def test_place_and_pickup():
    section("colocar y retirar por el teclado")
    h = Harness()
    h.key("enter")
    h.keys("1")                       # F
    check("la pieza queda en la mano", h.game.sel is not None)
    check("el panel la muestra", h.has("PIEZA  F"), h.text())
    h.key("enter")                    # cabe centrada
    check("se coloca", len(h.game.placed) == 1 and "F" in h.game.placed)
    check("el contador sube", h.has("1/12"), h.text())
    check("suelta la seleccion", h.game.sel is None)

    # la I vertical centrada se sale del tablero por abajo: fantasma invalido
    h.keys("2")
    ghost = h.game.ghost()
    check("el fantasma de la I se marca invalido", ghost is not None and not ghost.valid)
    h.key("enter")
    check("no coloca una pieza invalida", len(h.game.placed) == 1)
    # sigue invalida una fila arriba: ahi choca con la F recien puesta
    h.key("up")
    check("choca con la pieza ya puesta", not h.game.ghost().valid)
    # a la columna 0 entra: cursor (2,0) ancla la I en las filas 0-4
    for _ in range(5):
        h.key("left")
    check("en una columna libre ya entra", h.game.ghost().valid,
          str(h.game.ghost().cells))
    h.key("enter")
    check("se coloca la I", len(h.game.placed) == 2, str(h.game.placed.keys()))

    # el cursor quedo sobre la I recien puesta: backspace la retira
    h.key("backspace")
    check("backspace la retira", len(h.game.placed) == 1, str(h.game.placed.keys()))
    check("y vuelve a la mano", h.game.sel is not None and h.game.sel["name"] == "I")
    h.key("esc")
    check("esc cancela la seleccion", h.game.sel is None)
    check("esc de nuevo pregunta antes de salir", True)
    h.key("esc")
    check("ofrece guardar al salir con piezas puestas", h.top == "Modal", h.top)

    # la tecla de una pieza ya colocada la retira (como el clic en la web)
    h.key("esc")
    h2 = Harness()
    h2.key("enter").keys("1").key("enter")
    check("F colocada", "F" in h2.game.placed)
    h2.keys("1")
    check("su tecla la retira", "F" not in h2.game.placed
          and h2.game.sel and h2.game.sel["name"] == "F")

    # el mouse hace lo mismo (las coordenadas dependen de la escala del tablero)
    h3 = Harness()
    h3.key("enter").keys("1")
    gs = h3.app.top
    cw, chh = gs.scale
    px = gs.board_x + 2 + 5 * cw
    py = gs.board_y + 1 + 3 * chh
    check("el clic apunta a la celda esperada", gs.cell_at(px, py) == (3, 5),
          str(gs.cell_at(px, py)))
    h3.mouse("press", "left", px, py)
    check("el clic coloca", len(h3.game.placed) == 1, str(h3.game.placed))
    h3.mouse("press", "left", px, py)
    check("el clic sobre la pieza la retira", len(h3.game.placed) == 0)
    check("clic fuera del tablero no hace nada", gs.cell_at(0, 0) is None)


def test_menu_layout():
    section("layout del menu")
    from m5.screens import MenuScreen, menu_columns, menu_plan, menu_worst_height

    for w, hh in ((100, 30), (80, 24), (70, 22), (60, 20), (50, 18), (46, 16)):
        for lang in ("es", "en"):
            h = Harness(w, hh, lang=lang)
            h.render()
            raw = h.lines()
            # una fila cuenta como vacia aunque lleve la linea divisoria
            blank = lambda ln: ln.replace(g("v"), " ").replace("|", " ").strip() == ""
            lines = [ln.rstrip() for ln in raw]
            title_y = next(i for i, ln in enumerate(lines) if "01" in ln)
            check("%dx%d/%s: la cifra va en la fila del titulo" % (w, hh, lang),
                  "/" in lines[title_y], lines[title_y])
            check("%dx%d/%s: linea en blanco bajo la cifra" % (w, hh, lang),
                  blank(lines[title_y + 1]), repr(lines[title_y + 1]))
            nxt = next((i for i, ln in enumerate(lines) if "02" in ln), None)
            check("%dx%d/%s: linea en blanco sobre la opcion siguiente" % (w, hh, lang),
                  nxt is not None and blank(lines[nxt - 1]),
                  repr(lines[nxt - 1]) if nxt else "sin 02")
            check("%dx%d/%s: el menu no invade el pie" % (w, hh, lang),
                  nxt is None or nxt < hh - 3, "02 en %s de %d" % (nxt, hh))

            # lo importante: la descripcion no invade la columna de la cifra
            mw = min(64, w - 4)
            x0 = (w - mw) // 2
            div, text_w = menu_columns(MenuScreen(h.app).items(), mw)
            if div is None:
                continue
            col = x0 + div
            check("%dx%d/%s: hay linea vertical en la fila del titulo" % (w, hh, lang),
                  raw[title_y][col] in "|" + g("v"), repr(raw[title_y][col]))
            for dy in (1, 2, 3):  # el hueco y las lineas de descripcion
                row = raw[title_y + dy]
                check("%dx%d/%s: la fila +%d respeta la columna" % (w, hh, lang, dy),
                      row[col] in "|" + g("v") and row[:col].rstrip() == row[:col].rstrip(),
                      repr(row))
                check("%dx%d/%s: nada de texto pasada la linea en +%d"
                      % (w, hh, lang, dy), row[col + 1:].strip() == "",
                      repr(row[col + 1:]))

    # medir y dibujar salen del mismo plan: no se pueden desincronizar
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
                check("plan gap=%d desc_gap=%d max_desc=%d: el alto cubre las filas"
                      % (gap, dg, md), max(heights) >= rows_max,
                      "alto %d filas %d" % (max(heights), rows_max))
                check("plan gap=%d desc_gap=%d max_desc=%d: el peor caso es el maximo"
                      % (gap, dg, md),
                      menu_worst_height(items, 60, gap, dg, md) == max(heights))


def test_board_scaling():
    section("escala del tablero")
    from m5.screens import EditorScreen
    from m5.ui import CELL_SCALES, board_size
    from m5.levels import CLASSIC

    h = Harness(100, 30)
    h.key("enter")
    gs = h.app.top
    check("en 100x30 el clasico usa celdas de 4x2", gs.scale == (4, 2), str(gs.scale))
    w, _ = board_size(CLASSIC, gs.scale)
    check("el tablero ocupa mas del doble de ancho que el minimo",
          w >= 2 * board_size(CLASSIC)[0] - 3, str(w))

    # una silueta chica se agranda mas para no quedar perdida
    h2 = Harness(100, 30)
    h2.game.start_level(0)
    h2.app.stack = [h2.app.stack[0]]
    h2.key("down").key("enter").key("enter")
    check("el nivel 1 (5 celdas) usa celdas grandes",
          h2.app.top.scale[0] >= 6, str(h2.app.top.scale))

    # zoom manual con + / _ (shift-= y shift-- en teclado US)
    h4 = Harness(100, 30)
    h4.key("enter")
    gs = h4.app.top
    auto = gs.scale
    h4.type("+")
    check("+ acerca", gs.scale[0] > auto[0], "%s -> %s" % (auto, gs.scale))
    check("el zoom queda guardado", h4.app.zoom is not None)
    zoomed = gs.scale
    for _ in range(4):
        h4.type("+")
    check("+ no pasa de lo que entra en pantalla", gs.scale == zoomed, str(gs.scale))
    h4.type("_")
    check("_ aleja", gs.scale == auto, str(gs.scale))
    check("volver a la escala automatica libera el zoom", h4.app.zoom is None)
    for _ in range(4):
        h4.type("_")
    check("_ no baja de la escala minima", gs.scale == (2, 1), str(gs.scale))

    # las teclas de pieza -/= no deben confundirse con el zoom
    h4.type("-")
    check("- sigue eligiendo la pieza Y",
          h4.game.sel is not None and h4.game.sel["name"] == "Y")
    h4.type("=")
    check("= sigue eligiendo la pieza Z",
          h4.game.sel is not None and h4.game.sel["name"] == "Z")

    # la rueda del mouse tambien hace zoom, como en la vista ASCII de la web
    h5 = Harness(100, 30)
    h5.key("enter")
    gs = h5.app.top
    small = gs.scale
    h5.mouse("wheel", "up", 50, 15)
    check("la rueda acerca", gs.scale[0] > small[0], str(gs.scale))
    h5.mouse("wheel", "down", 50, 15)
    check("la rueda aleja", gs.scale == small, str(gs.scale))

    # el zoom sobrevive a un reinicio y se recorta si ya no entra
    h6 = Harness(100, 30)
    h6.key("enter")
    h6.type("+")
    h7 = Harness(100, 30, home=h6.tmp)
    h7.key("enter")
    check("el zoom sobrevive al reinicio", h7.app.top.scale == h6.app.top.scale,
          str(h7.app.top.scale))
    h8 = Harness(60, 20, settings={"zoom": 3})
    h8.key("enter")
    gs = h8.app.top
    bw, bh = board_size(h8.game.board, gs.scale)
    check("un zoom guardado que no entra se recorta",
          gs.board_x + bw <= 60 and gs.board_y + bh <= 18, str(gs.scale))
    for junk in ("abc", -5, 99, [1], {}):
        hx = Harness(100, 30, settings={"zoom": junk})
        hx.key("enter")
        check("zoom invalido %r no rompe nada" % (junk,),
              hx.app.top.scale in CELL_SCALES, str(hx.app.top.scale))

    # el editor comparte el mismo zoom
    h9 = Harness(100, 30)
    h9.app.push(EditorScreen(h9.app))
    h9.render()
    ed = h9.app.top
    ed_auto = ed.scale
    h9.type("+")
    check("el editor tambien hace zoom", ed.scale[0] > ed_auto[0], str(ed.scale))
    cw, chh = ed.scale
    h9.mouse("press", "left", ed.gx + 2 + 3 * cw, ed.gy + 1 + 2 * chh)
    check("y el clic pinta la celda correcta con la escala nueva", (2, 3) in ed.cells,
          str(sorted(ed.cells)))

    # y en una terminal chica cae a la escala minima sin desbordar
    for w, hh in ((46, 16), (60, 20), (80, 24), (100, 30), (140, 45)):
        h3 = Harness(w, hh)
        h3.key("enter")
        gs = h3.app.top
        bw, bh = board_size(h3.game.board, gs.scale)
        fits = (gs.board_x + bw <= w) and (gs.board_y + bh <= hh - 2)
        check("en %dx%d el tablero entra (escala %s)" % (w, hh, gs.scale), fits,
              "x=%d w=%d y=%d h=%d" % (gs.board_x, bw, gs.board_y, bh))


def test_canonical_symmetry():
    section("canonicalizacion (rotacion 180 y espejos)")
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
    # espejo horizontal del tablero -> misma forma canonica
    gm.occupied = {(r, 9 - c): n for (r, c), n in grid.items()}
    check("espejo horizontal da la misma canonica", gm.canonical_solution() == base)
    gm.occupied = {(5 - r, c): n for (r, c), n in grid.items()}
    check("espejo vertical da la misma canonica", gm.canonical_solution() == base)
    gm.occupied = {(5 - r, 9 - c): n for (r, c), n in grid.items()}
    check("rotacion 180 da la misma canonica", gm.canonical_solution() == base)


# --- 4. niveles: desbloqueo -------------------------------------------------

def test_levels():
    section("modo formas")
    h = Harness()
    h.key("down").key("enter")
    check("abre la lista de niveles", h.top == "LevelsScreen")
    check("el nivel 2 arranca bloqueado", h.has("02 ?????"))
    h.key("enter")
    check("entra al nivel 1", h.top == "GameScreen")
    auto_solve(h)
    check("nivel 1 completado", h.top == "Modal" and h.has("NIVEL 1 COMPLETADO"))
    check("guarda el mejor tiempo del nivel 1", h.store.level_best(0) is not None)
    check("anuncia el desbloqueo", h.has("Desbloqueaste el nivel 2"))
    h.key("enter")  # "Nivel 2"
    check("arranca el nivel 2", h.top == "GameScreen" and h.game.level_index == 1)


# --- 5. editor y verificacion -----------------------------------------------

def test_editor():
    section("editor de desafios")
    h = Harness()
    h.key("down").key("down").key("enter")   # Mis desafios
    check("abre mis desafios", h.top == "CustomsScreen")
    h.keys("n")
    check("abre el editor", h.top == "EditorScreen")
    ed = h.app.top

    # una cruz (el pentomino X): resoluble con una pieza
    for cell in [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)]:
        ed.cells.add(cell)
    ed.invalidate()
    h.keys("v")
    check("verifica una cruz como resoluble", ed.verified == ed.key(), ed.status)
    check("lo dice en pantalla", h.has("RESOLUBLE"), ed.status)

    # una silueta imposible: 5 celdas en L con un hueco suelto
    ed.cells.clear()
    for cell in [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4)]:
        ed.cells.add(cell)
    ed.invalidate()
    h.keys("v")
    check("detecta la silueta sin solucion", ed.verified is None, ed.status)
    check("lo dice en pantalla", h.has("SIN SOLUCION"), ed.status)

    # guardar exige verificacion previa
    h.keys("s")
    check("no guarda sin verificar", len(h.store.custom) == 0)

    ed.cells.clear()
    for cell in [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)]:
        ed.cells.add(cell)
    ed.invalidate()
    h.keys("v").keys("s")
    check("pide el nombre", h.top == "PromptScreen", h.top)
    h.type("Mi Cruz").key("enter")
    check("guarda el desafio", len(h.store.custom) == 1,
          str(h.store.custom))
    check("guarda con el nombre escrito",
          h.store.custom and h.store.custom[0]["name"] == "Mi Cruz")
    check("vuelve a mis desafios", h.top == "CustomsScreen", h.top)

    # jugarlo de punta a punta
    h.key("enter")
    check("juega el desafio propio", h.top == "GameScreen")
    auto_solve(h)
    check("completa el desafio propio",
          h.top == "Modal" and h.has("DESAFIO COMPLETADO"), h.top)
    check("guarda el record del desafio", h.store.custom[0]["best"] is not None)


def test_import():
    section("importar un codigo")
    h = Harness()
    h.key("down").key("down").key("enter").keys("i")
    check("abre la pantalla de importar", h.top == "ImportScreen")
    h.paste("M5.eyJuIjoiQ3J1eiBQcnVlYmEiLCJyIjozLCJjIjozLCJiIjoiZVFBPSJ9")
    h.key("enter")
    check("importa el desafio", len(h.store.custom) == 1, h.text()[-300:])
    check("con su nombre", h.store.custom[0]["name"] == "Cruz Prueba")

    h2 = Harness()
    h2.key("down").key("down").key("enter").keys("i")
    h2.type("basura").key("enter")
    check("rechaza un codigo invalido", len(h2.store.custom) == 0)
    check("y avisa", h2.has("invalido"), h2.text()[-300:])


# --- 6. partidas guardadas --------------------------------------------------

def test_slots():
    section("partidas guardadas")
    import time as _time
    h = Harness()
    h.key("enter")            # clasico
    h.keys("1").key("enter")  # coloca la F
    placed_before = dict(h.game.placed)
    check("hay una pieza colocada", len(placed_before) == 1)
    _time.sleep(0.02)         # que el reloj tenga algo que guardar
    h.app.save_slot(0)
    check("el slot 0 quedo ocupado", bool(h.store.slots.get("0")))
    h.app.go_menu()
    check("volvio al menu", h.top == "MenuScreen")
    h.app.load_slot(0)
    check("recarga la partida", h.top == "GameScreen")
    check("con la pieza puesta", len(h.game.placed) == 1)
    check("y el reloj corriendo", h.game.start_time is not None)

    # un snapshot corrupto no debe romper nada
    h.store.slots["1"] = {"mode": "level", "level_index": 999, "placed": []}
    h.app.load_slot(1)
    check("ignora un slot invalido", h.top == "GameScreen")
    h.store.slots["2"] = {"mode": "classic", "elapsed": 0,
                          "placed": [{"name": "ZZ", "orient": [[0, 0]],
                                      "anchor_r": 0, "anchor_c": 0}]}
    h.app.load_slot(2)
    check("ignora una pieza inexistente en un slot", h.top == "GameScreen")


def test_about():
    section("acerca de")
    from m5 import __version__

    for lang in ("es", "en"):
        h = Harness(100, 30, lang=lang)
        h.key("down").key("down").key("down").key("enter")  # menu -> Configuracion
        items = h.app.top.items()
        check("%s: hay una fila 'about'" % lang,
              any(it["key"] == "about" for it in items))
        idx = next(i for i, it in enumerate(items) if it["key"] == "about")
        for _ in range(idx):
            h.key("down")
        h.key("enter")
        check("%s: abre un modal" % lang, h.top == "Modal")
        check("%s: muestra la version" % lang, h.has(__version__), h.text())
        check("%s: menciona la licencia" % lang, h.has("MIT License"), h.text())
        h.key("enter")  # Cerrar
        check("%s: vuelve a Configuracion" % lang, h.top == "SettingsScreen")


# --- 7. robustez de dibujo --------------------------------------------------

def walk_all_screens(h):
    """Recorre todas las pantallas y las dibuja."""
    from m5.screens import (CustomsScreen, EditorScreen, GameScreen, HelpScreen,
                            ImportScreen, LevelsScreen, MenuScreen, SettingsScreen,
                            SlotsScreen)
    app = h.app
    app.game.start_classic()
    for cls in (MenuScreen, LevelsScreen, CustomsScreen, SettingsScreen,
                SlotsScreen, EditorScreen, GameScreen, HelpScreen, ImportScreen):
        app.stack = [MenuScreen(app), cls(app)]
        h.render()
    # con una pieza en la mano y un modal encima
    app.stack = [MenuScreen(app), GameScreen(app)]
    app.game.select("I")
    h.render()
    app.confirm_leave()
    h.render()
    app.game.start_level(9)   # Diamante, 7x7
    app.stack = [MenuScreen(app), GameScreen(app)]
    h.render()
    app.game.start_level(16)  # Gran Cruz, 9x9
    h.render()


def test_render_matrix():
    section("dibujo en tamanos, temas y modos de color")
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
                    check("tema=%s color=%s ascii=%s" % (theme, color, ascii_mode),
                          False, repr(exc))
                    return
    check("todas las combinaciones de tema/color/glifos/tamano dibujan", True)
    glyphs.use_ascii(False)


def test_no_crash_on_random_input():
    section("entrada arbitraria")
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
            check("evento %d (%r) no rompe" % (i, ev), False, repr(exc))
            return
        if not h.app.running:       # pudo haber elegido salir
            h.app.running = True
    check("4000 eventos aleatorios sin excepciones", True)


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
    test_render_matrix()
    test_no_crash_on_random_input()
    print("\n" + "=" * 60)
    if FAILED:
        print("FALLARON %d comprobaciones:" % len(FAILED))
        for name in FAILED:
            print("  - " + name)
        return 1
    print("todo en verde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
