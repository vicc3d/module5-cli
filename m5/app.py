"""La aplicacion: pila de pantallas, bucle principal y las reglas de
finalizacion (soluciones unicas del clasico, records, desbloqueos).
"""

import time

from .game import Game, fmt_ms, fmt_time
from .glyphs import g
from .i18n import level_name, set_lang, t
from .levels import CLASSIC_SOLUTIONS, CLASSIC_VARIANTS, LEVELS
from .screens import (
    MIN_H,
    MIN_W,
    GameScreen,
    MenuScreen,
    Modal,
    SlotsScreen,
    TooSmallScreen,
)
from .store import Store, save_path
from .term import BOLD, DIM
from .theme import get_theme


class App:
    def __init__(self, term, store=None):
        self.term = term
        self.store = store or Store()
        set_lang(self.store.settings.get("lang") or "en")
        self.game = Game()
        self.theme = None
        self.apply_theme()
        self.stack = [MenuScreen(self)]
        self.running = True
        self.toast = None          # (texto, vence_en, color_key)
        self._too_small = TooSmallScreen(self)
        # zoom del tablero: None = escala automatica, o un indice de CELL_SCALES
        zoom = self.store.settings.get("zoom")
        self.zoom = int(zoom) if isinstance(zoom, (int, float)) else None

    # --- tema ---------------------------------------------------------------

    def apply_theme(self):
        self.theme = get_theme(self.store.settings.get("theme", "neon"),
                               self.term.pal.mode)
        self.term.screen.force_redraw()

    def save_path_short(self):
        path = save_path()
        import os
        home = os.path.expanduser("~")
        return path.replace(home, "~") if path.startswith(home) else path

    # --- pila de pantallas --------------------------------------------------

    def push(self, screen):
        self.stack.append(screen)

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()

    def replace(self, screen):
        self.stack[-1] = screen

    def go_menu(self):
        self.game.mode = None
        self.stack = [MenuScreen(self)]

    @property
    def top(self):
        return self.stack[-1]

    # --- zoom del tablero ---------------------------------------------------

    def set_zoom(self, value):
        """Fija el zoom manual (o None para volver a la escala automatica)."""
        self.zoom = value
        self.store.settings["zoom"] = value
        self.store.persist()
        self.term.screen.force_redraw()

    # --- avisos efimeros ----------------------------------------------------

    def notify(self, text, kind="ok", seconds=2.5):
        self.toast = (text, time.monotonic() + seconds, kind)

    def _draw_toast(self, scr):
        if not self.toast:
            return
        text, until, kind = self.toast
        if time.monotonic() > until:
            self.toast = None
            return
        theme = self.theme
        color = {"ok": theme.ok, "bad": theme.bad, "warn": theme.warn}.get(kind, theme.accent)
        label = " %s " % text
        x = max(0, (scr.w - len(label)) // 2)
        y = max(0, scr.h - 2)
        scr.put(x, y, label, color, theme.panel, BOLD)

    # --- render -------------------------------------------------------------

    def render_once(self):
        term = self.term
        scr = term.screen
        if scr.w < MIN_W or scr.h < MIN_H:
            self._too_small.draw(scr)
        else:
            # se dibuja desde la ultima pantalla no-overlay hacia arriba
            base = 0
            for i in range(len(self.stack) - 1, -1, -1):
                if not self.stack[i].overlay:
                    base = i
                    break
            for screen in self.stack[base:]:
                screen.draw(scr)
            self._draw_toast(scr)
        term.present()

    # --- bucle principal ----------------------------------------------------

    def run(self):
        term = self.term
        term.sync_size()
        while self.running:
            if term.resized:
                term.sync_size()
                term.screen.force_redraw()
            self.render_once()
            for ev in term.poll(0.1):
                self.dispatch(ev)
                if not self.running:
                    break

    def dispatch(self, ev):
        name = getattr(ev, "name", None)
        if name == "ctrl-c":
            self.running = False
            return
        if name == "ctrl-l":
            self.term.screen.force_redraw()
            return
        scr = self.term.screen
        if scr.w < MIN_W or scr.h < MIN_H:
            self._too_small.handle(ev)
            return
        self.top.handle(ev)

    # --- salir --------------------------------------------------------------

    def confirm_quit(self):
        def do_quit():
            self.running = False
        self.push(Modal(self, t("quit_title"), [t("confirm_quit")],
                        [(t("yes"), do_quit), (t("no"), None)], klass="warn"))

    def confirm_leave(self):
        """Volver al menu desde una partida: ofrece guardarla si hay algo que
        perder (igual que confirmLeaveToMenu() en la version web)."""
        if self.game.mode is None or not self.game.occupied:
            self.go_menu()
            return
        self.push(Modal(
            self, t("leave_title"), [t("leave_body")],
            [(t("save_and_exit"), self.save_and_exit),
             (t("exit_without_saving"), self.go_menu),
             (t("cancel_leave"), None)],
            klass="warn",
        ))

    # --- partidas guardadas -------------------------------------------------

    def save_and_exit(self):
        slot = self.game.current_slot
        if slot is None:
            slot = next((i for i in range(5) if not self.store.slots.get(str(i))), None)
        if slot is None:
            # los 5 slots ocupados y esta partida no venia de ninguno: que el
            # usuario elija cual reemplazar
            self.notify(t("no_free_slot"), "warn")
            self.push(SlotsScreen(self))
            return
        self.save_slot(slot)
        self.go_menu()

    def save_slot(self, i):
        snap = self.game.snapshot()
        if not snap:
            return
        self.store.slots[str(i)] = snap
        self.game.current_slot = i
        self.store.persist()
        self.notify(t("saved_to_slot", i + 1))

    def load_slot(self, i):
        snap = self.store.slots.get(str(i))
        if not snap:
            return
        if not self.game.restore(snap):
            self.notify(t("invalid_code"), "bad")
            return
        self.game.current_slot = i
        self.stack = [MenuScreen(self), GameScreen(self)]

    # --- finalizacion -------------------------------------------------------

    def on_complete(self):
        gm = self.game
        elapsed = gm.elapsed()
        if gm.mode == "classic":
            self._complete_classic(elapsed)
        elif gm.mode == "custom":
            self._complete_custom(elapsed)
        else:
            self._complete_level(elapsed)

    def _copy_result(self, lines):
        text = " ".join(lines)
        return lambda: self.notify(
            t("code_copied") if self.term.copy(text) else t("code_copy_manual"))

    def _complete_classic(self, elapsed):
        store = self.store
        canon = self.game.canonical_solution()
        if canon in store.solutions:
            self.push(Modal(
                self, t("repeat_title"),
                [t("repeat_line1"),
                 t("repeat_line2", len(store.solutions), CLASSIC_SOLUTIONS)],
                [(t("find_another"), self.game.reset_board),
                 (t("menu_btn"), self.go_menu)],
                klass="warn",
            ))
            return
        store.solutions.append(canon)
        ms = int(elapsed * 1000)
        best = store.data.get("classic_best")
        is_record = best is None or ms < best
        if is_record:
            store.data["classic_best"] = ms
        store.persist()
        n = len(store.solutions)
        time_line = t("time_line", fmt_time(elapsed)) + (
            t("personal_record") if is_record else t("best_mark", fmt_ms(store.data["classic_best"])))
        self.push(Modal(
            self, t("win_solution", n),
            [time_line,
             t("classic_totals", CLASSIC_SOLUTIONS, CLASSIC_VARIANTS),
             t("remaining", CLASSIC_SOLUTIONS - n)],
            [(t("find_another_solution"), self.game.reset_board),
             (t("copy_result"), self._copy_result([t("win_solution", n), time_line])),
             (t("menu_btn"), self.go_menu)],
            klass="ok",
        ))

    def _complete_level(self, elapsed):
        store = self.store
        i = self.game.level_index
        ms = int(elapsed * 1000)
        prev = store.level_best(i)
        is_record = prev is None or ms < prev
        store.levels[str(i)] = {"best": ms if is_record else prev}
        store.persist()
        best = store.level_best(i)
        line = "%s%s%s %s %s%s" % (
            g("quote_l"), level_name(i, LEVELS[i].name), g("quote_r"),
            g("v"), t("time_line", fmt_time(elapsed)),
            t("record_mark") if is_record else t("best_mark", fmt_ms(best)),
        )
        buttons = []
        if i < len(LEVELS) - 1:
            buttons.append((t("next_level", i + 2), lambda: self._start_level(i + 1)))
        buttons.append((t("replay"), lambda: self._start_level(i)))
        buttons.append((t("menu_btn"), self.go_menu))
        lines = [line]
        lines.append(t("unlocked_next", i + 2) if i < len(LEVELS) - 1 else t("all_done"))
        self.push(Modal(self, t("level_complete", i + 1), lines, buttons, klass="ok"))

    def _start_level(self, i):
        self.game.start_level(i)
        self.stack = [MenuScreen(self), GameScreen(self)]

    def _complete_custom(self, elapsed):
        store = self.store
        ms = int(elapsed * 1000)
        created = self.game.board.created_at
        # se busca por created_at (identidad estable), no por posicion en la
        # lista: el desafio puede venir de un slot guardado
        entry = next((c for c in store.custom if c.get("created_at") == created), None)
        is_record = entry is not None and (not entry.get("best") or ms < entry["best"])
        if is_record:
            entry["best"] = ms
            store.persist()
        mark = ""
        if entry:
            mark = t("record_mark") if is_record else t("best_mark", fmt_ms(entry.get("best")))
        line = "%s%s%s %s %s%s" % (g("quote_l"), self.game.board.name, g("quote_r"),
                                   g("v"), t("time_line", fmt_time(elapsed)), mark)
        self.push(Modal(
            self, t("custom_complete"), [line],
            [(t("replay"), self._replay_custom),
             (t("my_challenges_btn"), self._go_customs),
             (t("menu_btn"), self.go_menu)],
            klass="ok",
        ))

    def _replay_custom(self):
        board = self.game.board
        self.game.start_custom({
            "name": board.name,
            "cells": [list(c) for c in board.cells],
            "created_at": board.created_at,
        })

    def _go_customs(self):
        from .screens import CustomsScreen
        self.game.mode = None
        self.stack = [MenuScreen(self), CustomsScreen(self)]
