"""The game's screens and the main loop.

Each screen knows how to draw itself onto the buffer and respond to an event.
They stack: the ones marked `overlay = True` (modals, help) paint on top of
the one below instead of replacing it.
"""

import time

from . import __version__, solver
from .game import Game, fmt_ms, fmt_time
from .glyphs import g
from .i18n import get_lang, level_name, plural, set_lang, t
from .levels import CLASSIC, CLASSIC_SOLUTIONS, CLASSIC_VARIANTS, LEVELS, Board
from .pieces import PIECE_KEYS, PIECE_NAMES
from .store import decode_challenge, encode_challenge
from .term import BOLD, DIM, REVERSE, UNDERLINE, Mouse, Paste
from .theme import THEME_ORDER, get_theme
from .ui import (
    CELL_W,
    TextField,
    board_size,
    box,
    draw_board,
    draw_cell,
    draw_minimap,
    draw_tray,
    hint,
    resolve_scale,
    scrim,
    wrap,
)

MIN_W, MIN_H = 46, 16

# Block typeface for the menu title (5 rows, 5 columns per letter).
FONT = {
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "D": ["#### ", "#   #", "#   #", "#   #", "#### "],
    "U": ["#   #", "#   #", "#   #", "#   #", " ### "],
    "L": ["#    ", "#    ", "#    ", "#    ", "#####"],
    "E": ["#####", "#    ", "#### ", "#    ", "#####"],
    "5": ["#####", "#    ", "#### ", "    #", "#### "],
    " ": ["     ", "     ", "     ", "     ", "     "],
}


def big_text(word):
    rows = [""] * 5
    for i, ch in enumerate(word):
        glyph = FONT.get(ch.upper(), FONT[" "])
        for r in range(5):
            rows[r] += ("" if i == 0 else " ") + glyph[r]
    return [row.replace("#", g("full")) for row in rows]


class ZoomMixin:
    """Manual zoom of the play area, shared by the board and the editor.

    On a US keyboard `+` is Shift-= and `_` is Shift--, exactly the two keys
    left free: `-` and `=` without Shift already select pieces Y and Z.
    """

    scale = (2, 1)
    scale_index = 0
    max_index = 0
    auto_index = 0

    def apply_scale(self, board, avail_w, avail_h):
        self.scale, self.scale_index, self.max_index, self.auto_index = resolve_scale(
            board, avail_w, avail_h, self.app.zoom)
        return self.scale

    def zoom_by(self, delta):
        idx = min(max(self.scale_index + delta, 0), self.max_index)
        if idx == self.scale_index:
            return  # already at the limit: nothing to report
        # if the manual zoom matches what the game would pick on its own, it
        # switches back to automatic mode so it keeps adapting on resize
        self.app.set_zoom(None if idx == self.auto_index else idx)
        if idx == self.auto_index:
            self.app.notify(t("zoom_auto"))
        else:
            self.app.notify(t("zoom_level", idx + 1, self.max_index + 1))

    def handle_zoom_key(self, ch):
        """True if the key was a zoom key."""
        if ch == "+":
            self.zoom_by(1)
            return True
        if ch == "_":
            self.zoom_by(-1)
            return True
        return False

    def handle_zoom_wheel(self, ev):
        """True if the event was the mouse wheel (zoom, like the web version)."""
        if getattr(ev, "kind", None) != "wheel":
            return False
        self.zoom_by(1 if ev.button == "up" else -1)
        return True


class Screen:
    """Base for all screens."""

    overlay = False

    def __init__(self, app):
        self.app = app

    @property
    def theme(self):
        return self.app.theme

    @property
    def game(self):
        return self.app.game

    @property
    def store(self):
        return self.app.store

    def draw(self, scr):
        raise NotImplementedError

    def handle(self, ev):
        return None


# Shared chrome

def header(scr, theme, title, right=None):
    w = scr.w
    scr.fill(0, 0, w, 1, " ", theme.text, theme.panel)
    x = scr.put(1, 0, "MODULE 5", theme.accent, theme.panel, BOLD)
    if title:
        x = scr.put(x, 0, "  " + g("v") + "  ", theme.border, theme.panel)
        scr.put(x, 0, title, theme.text_hi, theme.panel, BOLD)
    if right:
        scr.put(max(0, w - len(right) - 1), 0, right, theme.accent, theme.panel, BOLD)
    scr.fill(0, 1, w, 1, g("h"), theme.border, theme.bg)


def footer(scr, theme, pairs):
    y = scr.h - 1
    scr.fill(0, y, scr.w, 1, " ", theme.text_dim, theme.panel)
    hint(scr, 1, y, scr.w - 2, pairs, theme)


def menu_columns(items, w, min_text=24):
    """Splits the width between the text column and the value column.

    Returns (line_x, text_width) relative to the left margin, or
    (None, w - 4) if there's no room for two columns. The value lives to the
    right of a vertical line and the description never crosses it: if the
    text could continue below it, the two things would read as a single
    column.
    """
    note_w = max((len(item.get("note") or "") for item in items), default=0)
    if not note_w:
        return None, w - 4
    div = w - note_w - 3
    if div - 4 < min_text:
        return None, w - 4
    return div, div - 3


def menu_plan(items, index, w, gap=1, desc_gap=1, max_desc=2, text_w=None):
    """Computes the list's rows and their height, without drawing anything.

    Drawing and measuring both come from here so they can't get out of sync.
    `desc_gap` is the space around the description, above and below.
    """
    if text_w is None:
        text_w = menu_columns(items, w)[1]
    rows = []
    yy = 0
    step = 0
    for i, item in enumerate(items):
        rows.append((yy, "item", (i, item)))
        yy += 1
        step = gap
        desc = item.get("desc")
        if desc and i == index and max_desc:
            yy += desc_gap
            lines = wrap(desc, text_w)
            shown = lines[:max_desc]
            if len(lines) > max_desc and shown:
                # cut off for lack of height: make it clear it continues
                shown[-1] = shown[-1][:max(0, text_w - 3)].rstrip() + "..."
            for line in shown:
                rows.append((yy, "desc", line))
                yy += 1
            # the space below doesn't add to the between-options one: they overlap
            step = max(gap, desc_gap)
        yy += step
    return rows, yy - step  # the space left over after the last one doesn't count


def menu_worst_height(items, w, gap=1, desc_gap=1, max_desc=2):
    """The height with the tallest option active: the layout doesn't shift while navigating."""
    text_w = menu_columns(items, w)[1]
    return max(menu_plan(items, i, w, gap, desc_gap, max_desc, text_w)[1]
               for i in range(len(items))) if items else 0


def menu_rows(scr, theme, x, y, w, items, index, gap=1, desc_gap=1, max_desc=2):
    """Vertical list of options with a description; returns the height used."""
    div, text_w = menu_columns(items, w)
    rows, height = menu_plan(items, index, w, gap, desc_gap, max_desc, text_w)

    # the line runs the whole block's height: it separates the value column
    # from the text one, so the description doesn't look like it continues
    # below the value
    if div is not None:
        for dy in range(height):
            scr.put(x + div, y + dy, g("v"), theme.border, theme.bg)

    for dy, kind, payload in rows:
        yy = y + dy
        if kind == "desc":
            scr.put(x + 2, yy, payload, theme.text_dim, theme.bg, max_w=text_w)
            continue
        i, item = payload
        active = i == index
        disabled = item.get("disabled")
        note = item.get("note")
        if active:
            # the highlight stops at the line: it doesn't cross it
            scr.fill(x, yy, div if div is not None else w, 1, " ", theme.text, theme.panel)
            scr.put(x, yy, g("right"), theme.accent, theme.panel, BOLD)
        bg = theme.panel if active else theme.bg
        fg = theme.text_dim if disabled else (theme.text_hi if active else theme.text)
        scr.put(x + 2, yy, item["label"], fg, bg, BOLD if active else 0, max_w=text_w)
        if note:
            note_fg = theme.accent if active else theme.text_dim
            if div is not None:
                scr.put(x + div + 2, yy, note, note_fg, theme.bg,
                        BOLD if active else 0)
            else:
                scr.put(max(x + 2, x + w - len(note)), yy, note, note_fg, bg)
    return height


# Main menu

class MenuScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.index = 0

    def items(self):
        st = self.store
        return [
            {"key": "classic", "label": "01  " + t("classic_title"),
             "desc": t("classic_desc"),
             "note": t("stat_classic", len(st.solutions), CLASSIC_SOLUTIONS)},
            {"key": "shapes", "label": "02  " + t("shapes_title"),
             "desc": t("shapes_desc"),
             "note": t("stat_levels", len(st.levels), len(LEVELS))},
            {"key": "customs", "label": "03  " + t("my_challenges"),
             "desc": t("custom_empty") if not st.custom else
                     "%d %s" % (len(st.custom), t("my_challenges").lower()),
             "note": "%d" % len(st.custom)},
            {"key": "slots", "label": "04  " + t("saved_games_title_menu"),
             "desc": t("saved_games_desc_menu"),
             "note": "%d/5" % len([k for k in st.slots if st.slots[k]])},
            {"key": "settings", "label": "05  " + t("settings_title_menu"),
             "desc": t("settings_desc")},
            {"key": "quit", "label": "06  " + t("quit_title"),
             "desc": t("quit_desc")},
        ]

    # Layout variants (big logo, space between options, space around the
    # description, description lines), from the roomiest to the tightest: the
    # first one that fits above the footer line is used. The space around the
    # description is the last thing sacrificed, since it's exactly what keeps the
    # text from reading as glued to the value above it.
    LAYOUTS = [
        (True, 1, 1, 2), (False, 1, 1, 2), (False, 0, 1, 2), (False, 0, 1, 1),
        (False, 0, 0, 1), (False, 0, 0, 0),
    ]

    def draw(self, scr):
        theme = self.theme
        scr.clear(theme.bg)
        items = self.items()
        w = min(64, scr.w - 4)
        x = (scr.w - w) // 2
        limit = scr.h - 3  # the block has to end before the footer

        big, gap, desc_gap, max_desc = self.LAYOUTS[-1]
        for cand in self.LAYOUTS:
            top = 1 + (6 if cand[0] else 2) + 2
            # the gap after the last option is leftover space: it doesn't
            # have to fit above the footer, so it isn't counted
            h = menu_worst_height(items, w, cand[1], cand[2], cand[3])
            if top + h <= limit:
                big, gap, desc_gap, max_desc = cand
                break

        y = 1
        if big:
            for i, line in enumerate(big_text("MODULE 5")):
                scr.put_center(y + i, line, theme.accent, theme.bg, BOLD)
            y += 6
        else:
            scr.put_center(y, "MODULE 5", theme.accent, theme.bg, BOLD)
            y += 2
        scr.put_center(y, t("sys_line"), theme.text_dim, theme.bg)
        y += 2
        menu_rows(scr, theme, x, y, w, items, self.index, gap, desc_gap, max_desc)
        scr.put_center(scr.h - 3, t("foot_line"), theme.text_dim, theme.bg, DIM)
        footer(scr, theme, [
            (g("arrows")[1] + g("arrows")[2], t("keys_nav")),
            (g("enter"), t("keys_ok")),
            ("?", t("help_hint").split()[-1]),
            ("q", t("keys_quit")),
        ])

    def handle(self, ev):
        items = self.items()
        name = getattr(ev, "name", None)
        if name in ("up", "left"):
            self.index = (self.index - 1) % len(items)
        elif name in ("down", "right", "tab"):
            self.index = (self.index + 1) % len(items)
        elif name == "enter":
            self.activate(items[self.index]["key"])
        elif name == "char" and ev.char in "123456789"[:len(items)]:
            i = int(ev.char) - 1
            self.index = i
            self.activate(items[i]["key"])
        elif name == "char" and ev.char in "qQ":
            self.app.confirm_quit()
        elif name == "char" and ev.char == "?":
            self.app.push(HelpScreen(self.app))

    def activate(self, key):
        app = self.app
        if key == "classic":
            self.game.start_classic()
            app.push(GameScreen(app))
        elif key == "shapes":
            app.push(LevelsScreen(app))
        elif key == "customs":
            app.push(CustomsScreen(app))
        elif key == "slots":
            app.push(SlotsScreen(app))
        elif key == "settings":
            app.push(SettingsScreen(app))
        elif key == "quit":
            app.confirm_quit()


# Level selection

class LevelsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.index = 0

    def unlocked(self, i):
        return i == 0 or str(i - 1) in self.store.levels

    def draw(self, scr):
        theme = self.theme
        scr.clear(theme.bg)
        header(scr, theme, t("levels_head"),
               t("stat_levels", len(self.store.levels), len(LEVELS)))
        col_w = 22
        cols = max(1, min(4, (scr.w - 2) // col_w))
        rows = (len(LEVELS) + cols - 1) // cols
        avail = scr.h - 5
        if rows > avail:  # short terminal: more columns, fewer rows
            cols = max(1, min(6, (scr.w - 2) // 16))
            col_w = max(14, (scr.w - 2) // cols)
            rows = (len(LEVELS) + cols - 1) // cols
        self.cols = cols
        x0 = max(1, (scr.w - cols * col_w) // 2)
        for i, lv in enumerate(LEVELS):
            r, c = divmod(i, cols)
            x = x0 + c * col_w
            y = 3 + r
            if y >= scr.h - 2:
                break
            unlocked = self.unlocked(i)
            active = i == self.index
            best = self.store.level_best(i)
            num = "%02d" % (i + 1)
            label = level_name(i, lv.name) if unlocked else "?" * 5
            if active:
                scr.fill(x, y, col_w - 1, 1, " ", theme.text, theme.panel)
            bg = theme.panel if active else theme.bg
            fg = theme.text_dim if not unlocked else (theme.text_hi if active else theme.text)
            scr.put(x, y, num, theme.accent if unlocked else theme.text_dim, bg,
                    BOLD if active else 0)
            scr.put(x + 3, y, label[:col_w - 10], fg, bg, BOLD if active else 0)
            # only what's already solved gets a mark (with its best time); an
            # unlocked but unsolved level carries no mark, and the locked one
            # is already set apart by its hidden name
            if best:
                mark = fmt_ms(best)
                scr.put(x + col_w - 2 - len(mark), y, mark, theme.ok, bg)
        lv = LEVELS[self.index]
        info_y = scr.h - 3
        if self.unlocked(self.index):
            info = "%s %s %s %s %d %s" % (
                level_name(self.index, lv.name), g("v"), plural(lv.pieces),
                g("v"), len(lv.cells), t("cells_word"))
        else:
            info = t("locked")
        scr.put_center(info_y, info, theme.text_dim, theme.bg)
        footer(scr, theme, [
            (g("arrows"), t("keys_nav")),
            (g("enter"), t("play")),
            ("c", t("my_challenges")),
            ("esc", t("keys_back")),
        ])

    def handle(self, ev):
        name = getattr(ev, "name", None)
        cols = getattr(self, "cols", 4)
        n = len(LEVELS)
        if name == "left":
            self.index = (self.index - 1) % n
        elif name == "right":
            self.index = (self.index + 1) % n
        elif name == "up":
            self.index = (self.index - cols) % n
        elif name == "down":
            self.index = (self.index + cols) % n
        elif name == "home":
            self.index = 0
        elif name == "end":
            self.index = n - 1
        elif name == "enter":
            if self.unlocked(self.index):
                self.game.start_level(self.index)
                self.app.replace(GameScreen(self.app))
        elif name == "esc":
            self.app.pop()
        elif name == "char" and ev.char in "cC":
            self.app.push(CustomsScreen(self.app))
        elif name == "char" and ev.char == "?":
            self.app.push(HelpScreen(self.app))


# My challenges

class CustomsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.index = 0
        self.scroll = 0

    def entries(self):
        return self.store.custom

    def draw(self, scr):
        theme = self.theme
        scr.clear(theme.bg)
        header(scr, theme, t("my_challenges"), "%d" % len(self.entries()))
        items = self.entries()
        list_h = max(1, scr.h - 6)
        if self.index < self.scroll:
            self.scroll = self.index
        elif self.index >= self.scroll + list_h:
            self.scroll = self.index - list_h + 1
        if not items:
            for i, line in enumerate(wrap(t("custom_empty"), min(60, scr.w - 4))):
                scr.put_center(4 + i, line, theme.text_dim, theme.bg)
        for vi in range(self.scroll, min(len(items), self.scroll + list_h)):
            ch = items[vi]
            y = 3 + vi - self.scroll
            active = vi == self.index
            w = min(66, scr.w - 4)
            x = max(1, (scr.w - w) // 2)
            if active:
                scr.fill(x, y, w, 1, " ", theme.text, theme.panel)
                scr.put(x, y, g("right"), theme.accent, theme.panel, BOLD)
            bg = theme.panel if active else theme.bg
            scr.put(x + 2, y, ch["name"][:28], theme.text_hi if active else theme.text,
                    bg, BOLD if active else 0)
            n = len(ch["cells"])
            meta = "%s %s %d %s" % (plural(n // 5), g("v"), n, t("cells_word"))
            if ch.get("best"):
                meta += "  " + t("best_short", fmt_ms(ch["best"]))
            scr.put(max(x + 30, x + w - len(meta) - 1), y, meta, theme.text_dim, bg)
        footer(scr, theme, [
            (g("enter"), t("play")),
            ("n", t("create")),
            ("i", t("import_btn")),
            ("c", t("code")),
            ("d", t("delete")),
            ("esc", t("keys_back")),
        ])

    def handle(self, ev):
        name = getattr(ev, "name", None)
        items = self.entries()
        app = self.app
        if name == "up":
            self.index = max(0, self.index - 1)
        elif name == "down":
            self.index = min(max(0, len(items) - 1), self.index + 1)
        elif name == "esc":
            app.pop()
        elif name == "enter" and items:
            self.game.start_custom(items[self.index])
            app.replace(GameScreen(app))
        elif name == "char" and ev.char in "nN":
            app.push(EditorScreen(app))
        elif name == "char" and ev.char in "iI":
            app.push(ImportScreen(app))
        elif name == "char" and ev.char in "cC" and items:
            self.show_code(items[self.index])
        elif name == "char" and ev.char in "dD" and items:
            self.confirm_delete()
        elif name == "char" and ev.char == "?":
            app.push(HelpScreen(app))

    def show_code(self, ch):
        code = encode_challenge(ch)
        copied = self.app.term.copy(code)
        self.app.push(Modal(
            self.app,
            t("code_title"),
            [t("code_share", ch["name"]), "", code, "",
             t("code_copied") if copied else t("code_copy_manual")],
            [(t("close"), None)],
            wide=True,
        ))

    def confirm_delete(self):
        ch = self.entries()[self.index]
        def do_delete():
            try:
                self.store.custom.remove(ch)
            except ValueError:
                return
            self.store.persist()
            self.index = max(0, min(self.index, len(self.entries()) - 1))
        self.app.push(Modal(
            self.app, t("delete"),
            ['%s%s%s' % (g("quote_l"), ch["name"], g("quote_r"))],
            [(t("yes"), do_delete), (t("no"), None)],
            klass="warn",
        ))


# Game screen

PANEL_W = 26


class GameScreen(ZoomMixin, Screen):
    def __init__(self, app):
        super().__init__(app)
        self.board_x = 0
        self.board_y = 0

    def title(self):
        gm = self.game
        if gm.mode == "classic":
            return t("classic_hud")
        if gm.mode == "level":
            i = gm.level_index
            return t("level_hud", i + 1, level_name(i, LEVELS[i].name).upper())
        return t("custom_hud", gm.board.name.upper())

    def draw(self, scr):
        theme = self.theme
        gm = self.game
        scr.clear(theme.bg)
        header(scr, theme, self.title(), fmt_time(gm.elapsed()))

        # whether the side panel fits is decided with the board at its
        # minimum size, and the largest cell that fits is picked from what's
        # left: in a wide terminal the board looks big, not stranded in a corner
        min_w, _ = board_size(gm.board)
        show_panel = scr.w >= min_w + PANEL_W + 4
        area_w = scr.w - (PANEL_W + 2 if show_panel else 0)
        area_h = scr.h - 5
        self.apply_scale(gm.board, area_w - 2, area_h)
        bw, bh = board_size(gm.board, self.scale)
        self.board_x = max(0, (area_w - bw) // 2)
        self.board_y = max(2, 2 + (area_h - bh) // 2)
        ghost = gm.ghost()
        draw_board(scr, self.board_x, self.board_y, gm, theme, ghost,
                   scale=self.scale)

        if show_panel:
            self.draw_panel(scr, scr.w - PANEL_W - 1, 3, PANEL_W)

        tray_y = scr.h - 3
        scr.fill(0, tray_y, scr.w, 1, " ", theme.text, theme.panel)
        label = t("tray") + " "
        count = t("placed_count", len(gm.placed), gm.board.pieces)
        scr.put(1, tray_y, label, theme.text_dim, theme.panel)
        # the tray has to stop before the counter, or on a narrow terminal
        # the two overlap
        tray_x = 1 + len(label)
        tray_w = max(0, scr.w - tray_x - len(count) - 2)
        draw_tray(scr, tray_x, tray_y, tray_w, gm, theme)
        scr.put(max(0, scr.w - len(count) - 1), tray_y, count, theme.accent, theme.panel, BOLD)
        if not show_panel:
            info = "%s %s %s" % (plural(gm.board.pieces), g("v"),
                                 "%d %s" % (len(gm.board.cells), t("cells_word")))
            scr.put_center(scr.h - 2, info, theme.text_dim, theme.bg)

        footer(scr, theme, [
            (g("arrows"), t("keys_move")),
            ("1-=", t("keys_pick")),
            ("r", t("keys_rotate")),
            ("f", t("keys_flip")),
            (g("enter"), t("keys_place")),
            ("bksp", t("keys_take")),
            ("+/_", t("keys_zoom")),
            ("o", t("keys_settings")),
            ("esc", t("keys_menu")),
        ])

    def panel_body(self):
        """The panel's sections, already resolved, so they can be measured
        before drawing the box."""
        gm = self.game
        # the minimap is shown at full resolution now (one line per board
        # row), so its height is just the board's own row count and there's
        # no compression math left
        sil_h = gm.board.rows
        info = []
        if gm.mode == "classic":
            info = [t("info_classic1"), t("info_classic2"),
                    t("info_found", len(self.store.solutions))]
        else:
            info = [t("reproduce")]
            best = (self.store.level_best(gm.level_index) if gm.mode == "level"
                    else self._custom_best())
            if best:
                info.append(t("best_short", fmt_ms(best)))
        return sil_h, info

    def draw_panel(self, scr, x, y, w):
        theme = self.theme
        gm = self.game
        sil_h, info = self.panel_body()
        info_lines = []
        for line in info:
            info_lines.extend(wrap(line, w - 4))
        # top+bottom border, the minimap, a blank line, the placed-count
        # line, a blank line, then the info lines
        needed = 2 + sil_h + 1 + 1 + 1 + len(info_lines)
        h = max(6, min(needed, scr.h - y - 4))
        # the elapsed time already shows in the header; this box's title
        # doubles as the minimap's label instead of repeating the clock
        box(scr, x, y, w, h, theme, title=t("target"))
        bottom = y + h - 1

        def line(yy, text, fg, attr=0):
            if y < yy < bottom:
                scr.put(x + 2, yy, text[:w - 4], fg, theme.panel, attr)

        yy = y + 1
        if yy + sil_h - 1 < bottom:
            draw_minimap(scr, x + 2, yy, gm.board, theme, gm.occupied)
        yy += sil_h + 1
        line(yy, t("placed_count", len(gm.placed), gm.board.pieces), theme.text)
        yy += 2
        for chunk in info_lines:
            line(yy, chunk, theme.text_dim)
            yy += 1

    def _custom_best(self):
        ch = self._custom_entry()
        return ch.get("best") if ch else None

    def _custom_entry(self):
        created = self.game.board.created_at
        for ch in self.store.custom:
            if ch.get("created_at") == created:
                return ch
        return None

    # Interaction

    def handle(self, ev):
        gm = self.game
        app = self.app
        name = getattr(ev, "name", None)
        if isinstance(ev, Mouse):
            if self.handle_zoom_wheel(ev):
                return
            return self.handle_mouse(ev)
        if name == "up":
            gm.move_cursor(-1, 0)
        elif name == "down":
            gm.move_cursor(1, 0)
        elif name == "left":
            gm.move_cursor(0, -1)
        elif name == "right":
            gm.move_cursor(0, 1)
        elif name == "enter" or name == "space":
            self.try_place()
        elif name == "backspace" or name == "delete":
            gm.pickup_at_cursor()
        elif name == "tab":
            gm.cycle_selection(1)
        elif name == "shift-tab":
            gm.cycle_selection(-1)
        elif name == "esc":
            if gm.sel:
                gm.deselect()
            else:
                app.confirm_leave()
        elif name == "char":
            self.handle_char(ev.char)

    def handle_char(self, ch):
        gm = self.game
        low = ch.lower()
        if self.handle_zoom_key(ch):
            return
        if low == "r":
            gm.rotate()
        elif low == "f":
            gm.flip()
        elif low == "?":
            self.app.push(HelpScreen(self.app))
        elif low == "q":
            self.app.confirm_leave()
        elif low == "o":
            self.app.push(SettingsScreen(self.app))
        elif low == "x":
            if gm.occupied:
                self.app.push(Modal(
                    self.app, t("reset"),
                    [t("placed_count", len(gm.placed), gm.board.pieces)],
                    [(t("yes"), gm.reset_board), (t("no"), None)], klass="warn"))
        elif low in ("w", "a", "s", "d"):
            deltas = {"w": (-1, 0), "s": (1, 0), "a": (0, -1), "d": (0, 1)}
            gm.move_cursor(*deltas[low])
        else:
            for pname, pkey in PIECE_KEYS.items():
                if ch == pkey:
                    if pname in gm.placed:
                        # the piece is already on the board: take it back
                        # (equivalent to clicking the piece in the web version)
                        gm.pickup(pname)
                    elif gm.sel and gm.sel["name"] == pname:
                        gm.deselect()
                    else:
                        gm.select(pname)
                    return

    def try_place(self):
        gm = self.game
        if not gm.sel:
            gm.pickup_at_cursor()
            return
        if gm.place() and gm.is_complete():
            self.app.on_complete()

    def handle_mouse(self, ev):
        gm = self.game
        if ev.kind not in ("press", "drag"):
            return
        cell = self.cell_at(ev.x, ev.y)
        if cell is None:
            return
        if ev.button == "right":
            gm.deselect()
            return
        gm.set_cursor(*cell)
        if ev.kind == "drag":
            return
        if gm.sel:
            self.try_place()
        else:
            gm.pickup_at_cursor()

    def cell_at(self, x, y):
        """Converts screen coordinates to a board cell."""
        gm = self.game
        cw, chh = self.scale
        r = (y - self.board_y - 1) // chh
        c = (x - self.board_x - 2) // cw
        if y <= self.board_y or x <= self.board_x + 1:
            return None
        if 0 <= r < gm.board.rows and 0 <= c < gm.board.cols:
            return (r, c)
        return None


# Challenge editor

ED_ROWS, ED_COLS = 6, 10
# fictitious board the size of the grid, just to pick the scale
_ED_BOARD = Board("editor", [(r, c) for r in range(ED_ROWS) for c in range(ED_COLS)])


class EditorScreen(ZoomMixin, Screen):
    def __init__(self, app):
        super().__init__(app)
        self.cells = set()
        self.cursor = (0, 0)
        self.verified = None    # key of the silhouette verified as solvable
        self.status = ""
        self.status_kind = ""
        self.painting = None    # value being painted while dragging
        self.spinner = 0

    def key(self):
        return tuple(sorted(self.cells))

    def draw(self, scr):
        theme = self.theme
        scr.clear(theme.bg)
        header(scr, theme, t("create_challenge"),
               t("cells_line", len(self.cells)))
        # same automatic scale as the game board
        self.apply_scale(_ED_BOARD, scr.w - 4, scr.h - 9)
        cw, chh = self.scale
        bw = ED_COLS * cw + 3
        self.gx = max(0, (scr.w - bw) // 2)
        self.gy = 3
        self.draw_grid(scr, self.gx, self.gy)
        y = self.gy + ED_ROWS * chh + 3
        n = len(self.cells)
        ok_mult = n > 0 and n % 5 == 0
        line = t("pieces_line_ok", n // 5) if ok_mult else t("pieces_line_bad", "%.1f" % (n / 5))
        scr.put_center(y, line, theme.ok if ok_mult else theme.warn, theme.bg)
        if self.status:
            color = {"ok": theme.ok, "bad": theme.bad}.get(self.status_kind, theme.text_dim)
            scr.put_center(y + 1, self.status, color, theme.bg, BOLD)
        for i, chunk in enumerate(wrap(t("editor_hint"), min(70, scr.w - 4))):
            scr.put_center(scr.h - 3 + i, chunk, theme.text_dim, theme.bg)
        can_save = self.verified == self.key() and n > 0
        footer(scr, theme, [
            (g("arrows"), t("keys_move")),
            ("space", t("keys_paint")),
            ("v", t("verify")),
            ("s", t("save")) if can_save else ("c", t("clear")),
            ("+/_", t("keys_zoom")),
            ("esc", t("keys_back")),
        ])

    def draw_grid(self, scr, x, y):
        theme = self.theme
        cw, chh = self.scale
        bg = theme.board_bg
        inner = ED_COLS * cw + 1
        scr.put(x, y, g("dtl") + g("dh") * inner + g("dtr"), theme.border, bg)
        scr.put(x, y + ED_ROWS * chh + 1, g("dbl") + g("dh") * inner + g("dbr"),
                theme.border, bg)
        for r in range(ED_ROWS):
            for sub in range(chh):
                yy = y + 1 + r * chh + sub
                scr.put(x, yy, g("dv"), theme.border, bg)
                scr.put(x + inner + 1, yy, g("dv"), theme.border, bg)
                scr.put(x + 1, yy, " ", theme.text, bg)
            for c in range(ED_COLS):
                cx = x + 2 + c * cw
                cy = y + 1 + r * chh
                on = (r, c) in self.cells
                attr = REVERSE if self.cursor == (r, c) else 0
                if on and theme.tiles:
                    draw_cell(scr, cx, cy, cw, chh, "", theme.tile_text,
                              theme.accent, attr)
                elif on:
                    draw_cell(scr, cx, cy, cw, chh, "", theme.accent, bg,
                              attr | BOLD, body=g("full"))
                else:
                    draw_cell(scr, cx, cy, cw, chh, g("empty_cell"), theme.empty,
                              bg, attr)

    def handle(self, ev):
        name = getattr(ev, "name", None)
        if isinstance(ev, Mouse):
            return self.handle_mouse(ev)
        if name == "up":
            self.cursor = (max(0, self.cursor[0] - 1), self.cursor[1])
        elif name == "down":
            self.cursor = (min(ED_ROWS - 1, self.cursor[0] + 1), self.cursor[1])
        elif name == "left":
            self.cursor = (self.cursor[0], max(0, self.cursor[1] - 1))
        elif name == "right":
            self.cursor = (self.cursor[0], min(ED_COLS - 1, self.cursor[1] + 1))
        elif name in ("space", "enter"):
            self.toggle(self.cursor)
        elif name == "esc":
            self.app.pop()
        elif name == "char":
            self.handle_char(ev.char)

    def handle_char(self, ch):
        low = ch.lower()
        if self.handle_zoom_key(ch):
            return
        if low == "v":
            self.verify()
        elif low == "s":
            self.save()
        elif low == "c":
            self.cells.clear()
            self.invalidate()
        elif low == "?":
            self.app.push(HelpScreen(self.app))

    def handle_mouse(self, ev):
        if self.handle_zoom_wheel(ev):
            return
        cw, chh = self.scale
        if ev.y <= self.gy or ev.x <= self.gx + 1:
            return
        r = (ev.y - self.gy - 1) // chh
        c = (ev.x - self.gx - 2) // cw
        if not (0 <= r < ED_ROWS and 0 <= c < ED_COLS):
            return
        self.cursor = (r, c)
        if ev.kind == "press":
            self.painting = (r, c) not in self.cells
            self.toggle((r, c))
        elif ev.kind == "drag" and self.painting is not None:
            # dragging paints continuously, like the web version's editor
            if self.painting and (r, c) not in self.cells:
                self.cells.add((r, c))
                self.invalidate()
            elif not self.painting and (r, c) in self.cells:
                self.cells.discard((r, c))
                self.invalidate()
        elif ev.kind == "release":
            self.painting = None

    def toggle(self, cell):
        if cell in self.cells:
            self.cells.discard(cell)
        else:
            self.cells.add(cell)
        self.invalidate()

    def invalidate(self):
        self.verified = None
        self.status = ""
        self.status_kind = ""

    def cell_list(self):
        from .pieces import normalize_cells
        return list(normalize_cells(list(self.cells)))

    def verify(self):
        n = len(self.cells)
        if n == 0 or n % 5 or n > 60:
            self.status, self.status_kind = t("pieces_line_bad", "%.1f" % (n / 5)), "bad"
            return
        key = self.key()
        self.status, self.status_kind = t("verifying_big"), ""
        cancelled = [False]

        def on_tick(_nodes):
            # the solver hands control back to the renderer every so many
            # nodes: that's what spins the spinner and lets ESC cancel
            self.spinner += 1
            self.status = "%s %s  (%s)" % (
                t("verifying_big"), g("spinner")[self.spinner % len(g("spinner"))],
                t("verify_cancel_hint"))
            self.app.render_once()
            for ev in self.app.term.poll(0):
                if getattr(ev, "name", None) == "esc":
                    cancelled[0] = True
                    raise solver.Cancelled()

        try:
            solvable, timed_out = solver.check_solvable(
                self.cell_list(), time_limit=10.0, on_tick=on_tick)
        except solver.Cancelled:
            self.status, self.status_kind = t("verify_cancelled"), "bad"
            return
        if solvable:
            self.verified = key
            self.status, self.status_kind = t("solvable_ok"), "ok"
        elif timed_out:
            self.status, self.status_kind = t("verify_timeout"), "bad"
        else:
            self.status, self.status_kind = t("unsolvable"), "bad"

    def save(self):
        if self.verified != self.key() or not self.cells:
            self.status, self.status_kind = t("need_verify"), "bad"
            return
        default = t("challenge_default", len(self.store.custom) + 1)

        def commit(value):
            cells = self.cell_list()
            rows = max(c[0] for c in cells) + 1
            cols = max(c[1] for c in cells) + 1
            self.store.custom.append({
                "name": (value.strip() or default)[:24],
                "cells": [list(c) for c in cells],
                "rows": rows,
                "cols": cols,
                "best": None,
                "created_at": int(time.time() * 1000),
            })
            self.store.persist()
            self.app.pop()
            self.app.notify(t("imported", (value.strip() or default)[:24]))

        self.app.push(PromptScreen(self.app, t("name_prompt"), default, commit,
                                   max_len=24))


# Import a code

class ImportScreen(Screen):
    overlay = True

    def __init__(self, app):
        super().__init__(app)
        self.field = TextField("", max_len=400)
        self.status = ""
        self.status_kind = ""
        self.spinner = 0

    def draw(self, scr):
        theme = self.theme
        w = min(70, scr.w - 4)
        h = 9
        x = (scr.w - w) // 2
        y = max(1, (scr.h - h) // 2)
        box(scr, x, y, w, h, theme, title=t("import_btn"), double=True,
            color=theme.accent)
        scr.put(x + 2, y + 2, t("import_prompt"), theme.text, theme.panel)
        scr.fill(x + 2, y + 4, w - 4, 1, " ", theme.text, theme.bg)
        self.field.draw(scr, x + 2, y + 4, w - 4, theme)
        if self.status:
            color = {"ok": theme.ok, "bad": theme.bad}.get(self.status_kind, theme.text_dim)
            scr.put(x + 2, y + 6, self.status[:w - 4], color, theme.panel, BOLD)
        hint(scr, x + 2, y + h - 2, w - 4,
             [(g("enter"), t("import_btn")), ("esc", t("keys_back"))], theme)

    def handle(self, ev):
        name = getattr(ev, "name", None)
        if name == "esc":
            self.app.pop()
            return
        if name == "enter":
            self.do_import()
            return
        self.field.handle(ev)

    def do_import(self):
        ch = decode_challenge(self.field.value)
        if not ch:
            self.status, self.status_kind = t("invalid_code"), "bad"
            return
        self.status, self.status_kind = t("verifying_small"), ""

        def on_tick(_n):
            self.spinner += 1
            self.status = "%s %s" % (t("verifying_small"),
                                     g("spinner")[self.spinner % len(g("spinner"))])
            self.app.render_once()
            for ev in self.app.term.poll(0):
                if getattr(ev, "name", None) == "esc":
                    raise solver.Cancelled()

        try:
            solvable, timed_out = solver.check_solvable(
                [tuple(c) for c in ch["cells"]], time_limit=10.0, on_tick=on_tick)
        except solver.Cancelled:
            self.status, self.status_kind = t("verify_cancelled"), "bad"
            return
        if not solvable:
            self.status = t("import_timeout") if timed_out else t("import_unsolvable")
            self.status_kind = "bad"
            return
        self.store.custom.append(ch)
        self.store.persist()
        self.app.pop()
        self.app.notify(t("imported", ch["name"]))


# Settings

class SettingsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.index = 0

    def items(self):
        st = self.store
        theme_key = st.settings.get("theme", "neon")
        return [
            {"key": "lang", "label": t("language"),
             "note": "ESPANOL" if get_lang() == "es" else "ENGLISH"},
            {"key": "theme", "label": t("theme"),
             "note": theme_key.upper(), "desc": t(self.app.theme.desc_key)},
            {"key": "mouse", "label": "Mouse",
             "note": t("yes") if st.settings.get("mouse", True) else t("no")},
            # the count goes as a description, not as a value: in the value
            # column it would read as this row's setting, when it's actually
            # saying what would be lost by clearing it
            {"key": "clear", "label": t("clear_progress"),
             "desc": "%s %s %s" % (
                 t("stat_classic", len(st.solutions), CLASSIC_SOLUTIONS),
                 g("sep").strip(),
                 t("stat_levels", len(st.levels), len(LEVELS)))},
            {"key": "about", "label": t("about"), "desc": t("about_desc")},
        ]

    def draw(self, scr):
        theme = self.theme
        scr.clear(theme.bg)
        header(scr, theme, t("settings_title"))
        items = self.items()
        w = min(60, scr.w - 4)
        x = (scr.w - w) // 2
        menu_rows(scr, theme, x, 4, w, items, self.index)
        path_line = "save: " + self.app.save_path_short()
        scr.put_center(scr.h - 3, path_line, theme.text_dim, theme.bg, DIM)
        footer(scr, theme, [
            (g("arrows")[1] + g("arrows")[2], t("keys_nav")),
            (g("enter"), t("keys_ok")),
            ("esc", t("keys_back")),
        ])

    def handle(self, ev):
        name = getattr(ev, "name", None)
        items = self.items()
        if name == "up":
            self.index = (self.index - 1) % len(items)
        elif name in ("down", "tab"):
            self.index = (self.index + 1) % len(items)
        elif name == "esc":
            self.app.pop()
        elif name in ("enter", "right", "left", "space"):
            self.activate(items[self.index]["key"], -1 if name == "left" else 1)
        elif name == "char" and ev.char == "?":
            self.app.push(HelpScreen(self.app))

    def activate(self, key, step=1):
        st = self.store
        app = self.app
        if key == "lang":
            new = "en" if get_lang() == "es" else "es"
            set_lang(new)
            st.settings["lang"] = new
            st.persist()
        elif key == "theme":
            order = THEME_ORDER
            cur = st.settings.get("theme", "neon")
            i = order.index(cur) if cur in order else 0
            new = order[(i + step) % len(order)]
            st.settings["theme"] = new
            st.persist()
            app.apply_theme()
        elif key == "mouse":
            st.settings["mouse"] = not st.settings.get("mouse", True)
            st.persist()
            app.notify(t("yes") if st.settings["mouse"] else t("no"))
        elif key == "clear":
            def do_clear():
                st.clear_progress()
                app.notify(t("progress_cleared"))
            app.push(Modal(app, t("clear_progress"), [t("clear_progress_q")],
                           [(t("no"), None), (t("yes"), do_clear)], klass="warn"))
        elif key == "about":
            app.push(Modal(app, t("about"), [
                "Module 5 %s" % __version__,
                "",
                t("about_tagline"),
                "",
                "Victor Crespo · 3dvic.com",
                "MIT License",
            ], [(t("close"), None)]))


class SlotsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.index = 0

    def slot_label(self, i):
        snap = self.store.slots.get(str(i))
        if not snap:
            return t("empty")
        mode = snap.get("mode")
        if mode == "classic":
            what = t("mode_classic")
        elif mode == "custom":
            what = "%s %s" % (t("mode_custom"), snap.get("board", {}).get("name", ""))
        else:
            what = t("mode_level", snap.get("level_index", 0) + 1)
        return "%s  %s  %s" % (what, fmt_ms(snap.get("elapsed", 0)),
                               plural(len(snap.get("placed", []))))

    def draw(self, scr):
        theme = self.theme
        scr.clear(theme.bg)
        header(scr, theme, t("saved_games"))
        w = min(60, scr.w - 4)
        x = (scr.w - w) // 2
        for i in range(5):
            y = 4 + i * 2
            active = i == self.index
            if active:
                scr.fill(x, y, w, 1, " ", theme.text, theme.panel)
                scr.put(x, y, g("right"), theme.accent, theme.panel, BOLD)
            bg = theme.panel if active else theme.bg
            scr.put(x + 2, y, t("slot_name", i + 1),
                    theme.text_hi if active else theme.text, bg, BOLD if active else 0)
            label = self.slot_label(i).strip()
            scr.put(x + 12, y, label[:w - 14], theme.text_dim, bg)
        for i, chunk in enumerate(wrap(t("slots_hint"), min(60, scr.w - 4))):
            scr.put_center(scr.h - 4 + i, chunk, theme.text_dim, theme.bg)
        in_game = self.game.mode is not None
        pairs = []
        if in_game:
            pairs.append(("s", t("save_btn")))
        pairs += [("l", t("load_btn")), ("esc", t("keys_back"))]
        footer(scr, theme, pairs)

    def handle(self, ev):
        name = getattr(ev, "name", None)
        if name == "up":
            self.index = (self.index - 1) % 5
        elif name == "down":
            self.index = (self.index + 1) % 5
        elif name == "esc":
            self.app.pop()
        elif name == "char" and ev.char in "sS":
            self.app.save_slot(self.index)
        elif name in ("enter",) or (name == "char" and ev.char in "lL"):
            self.app.load_slot(self.index)


# Modals and help

class Modal(Screen):
    overlay = True

    def __init__(self, app, title, lines, buttons, klass="", wide=False):
        super().__init__(app)
        self.title = title
        self.lines = lines
        self.buttons = buttons          # [(label, callback | None)]
        self.klass = klass
        self.index = 0
        self.wide = wide

    def draw(self, scr):
        theme = self.theme
        w = min(76 if self.wide else 60, scr.w - 4)
        body = []
        for line in self.lines:
            if not line:
                body.append("")
            elif len(line) <= w - 6:
                body.append(line)
            else:
                body.extend(wrap(line, w - 6) if " " in line else
                            [line[i:i + w - 6] for i in range(0, len(line), w - 6)])
        h = min(scr.h - 2, len(body) + 6)
        x = (scr.w - w) // 2
        y = max(0, (scr.h - h) // 2)
        color = {"ok": theme.ok, "warn": theme.warn, "bad": theme.bad}.get(
            self.klass, theme.accent)
        scrim(scr, theme)
        box(scr, x, y, w, h, theme, double=True, color=color)
        scr.put_center(y + 1, self.title, color, theme.panel, BOLD, x0=x, w=w)
        for i, line in enumerate(body):
            if y + 3 + i >= y + h - 2:
                break
            scr.put(x + 3, y + 3 + i, line, theme.text, theme.panel)
        # buttons
        labels = [" %s " % b[0] for b in self.buttons]
        total = sum(len(s) + 2 for s in labels)
        bx = x + max(2, (w - total) // 2)
        by = y + h - 2
        for i, label in enumerate(labels):
            active = i == self.index
            scr.put(bx, by, label,
                    theme.tile_text if (active and theme.tiles) else
                    (theme.text_hi if active else theme.text_dim),
                    color if (active and theme.tiles) else theme.panel,
                    BOLD | (REVERSE if active and not theme.tiles else 0))
            bx += len(label) + 2

    def handle(self, ev):
        name = getattr(ev, "name", None)
        if name in ("left", "up"):
            self.index = (self.index - 1) % len(self.buttons)
        elif name in ("right", "down", "tab"):
            self.index = (self.index + 1) % len(self.buttons)
        elif name == "enter" or name == "space":
            self.activate(self.index)
        elif name == "esc":
            self.app.pop()
        elif name == "char":
            # a button's initial as its shortcut
            for i, (label, _) in enumerate(self.buttons):
                if label[:1].lower() == ev.char.lower():
                    self.activate(i)
                    return

    def activate(self, i):
        _, cb = self.buttons[i]
        self.app.pop()
        if cb:
            cb()


class PromptScreen(Screen):
    overlay = True

    def __init__(self, app, prompt, placeholder, on_accept, max_len=60):
        super().__init__(app)
        self.prompt = prompt
        # the field starts empty and the default value shows dimmed behind
        # it: typing shouldn't have to clear anything first
        self.placeholder = placeholder
        self.field = TextField("", max_len=max_len)
        self.on_accept = on_accept

    def draw(self, scr):
        theme = self.theme
        w = min(60, scr.w - 4)
        h = 7
        x = (scr.w - w) // 2
        y = max(0, (scr.h - h) // 2)
        box(scr, x, y, w, h, theme, double=True, color=theme.accent)
        scr.put(x + 2, y + 2, self.prompt, theme.text, theme.panel)
        if not self.field.value and self.placeholder:
            scr.fill(x + 2, y + 4, w - 4, 1, " ", theme.text, theme.bg)
            scr.put(x + 2, y + 4, self.placeholder[:w - 4], theme.text_dim,
                    theme.bg, DIM)
            scr.put(x + 2, y + 4, " ", theme.text_hi, theme.bg, REVERSE)
        else:
            self.field.draw(scr, x + 2, y + 4, w - 4, theme)
        hint(scr, x + 2, y + h - 2, w - 4,
             [(g("enter"), t("keys_ok")), ("esc", t("keys_back"))], theme)

    def handle(self, ev):
        name = getattr(ev, "name", None)
        if name == "esc":
            self.app.pop()
        elif name == "enter":
            value = self.field.value
            self.app.pop()
            self.on_accept(value)
        else:
            self.field.handle(ev)


class HelpScreen(Screen):
    overlay = True

    ROWS = [
        ("keys_move", "arrows / wasd"),
        ("keys_pick", "1..0 - = / tab"),
        ("keys_rotate", "r"),
        ("keys_flip", "f"),
        ("keys_place", "enter / space"),
        ("keys_take", "backspace"),
        ("keys_reset", "x"),
        ("keys_zoom", "+ / _  (shift-= / shift--)"),
        ("keys_settings", "o"),
        ("keys_menu", "esc"),
        ("keys_help", "?"),
    ]

    def draw(self, scr):
        theme = self.theme
        w = min(64, scr.w - 4)
        rows = self.ROWS
        h = min(scr.h - 2, len(rows) + 8)
        x = (scr.w - w) // 2
        y = max(0, (scr.h - h) // 2)
        box(scr, x, y, w, h, theme, double=True, color=theme.accent)
        scr.put_center(y + 1, t("help_title"), theme.accent, theme.panel, BOLD, x0=x, w=w)
        for i, (key, combo) in enumerate(rows):
            yy = y + 3 + i
            if yy >= y + h - 3:
                break
            scr.put(x + 3, yy, combo[:26], theme.accent, theme.panel, BOLD)
            scr.put(x + 31, yy, t(key)[:w - 34], theme.text, theme.panel)
        scr.put_center(y + h - 3,
                       "mouse: %s / %s / %s" % (t("keys_place"), t("keys_take"),
                                                t("keys_zoom")),
                       theme.text_dim, theme.panel)
        hint(scr, x + 3, y + h - 2, w - 6, [("esc", t("close"))], theme)

    def handle(self, ev):
        name = getattr(ev, "name", None)
        if name in ("esc", "enter", "space") or name == "char":
            self.app.pop()


class TooSmallScreen(Screen):
    """Shown when the terminal doesn't meet the minimum; disappears once enlarged."""

    def draw(self, scr):
        theme = self.theme
        scr.clear(theme.bg)
        scr.put_center(max(0, scr.h // 2 - 1), t("too_small")[:scr.w], theme.warn,
                       theme.bg, BOLD)
        msg = t("too_small_need", MIN_W, MIN_H, scr.w, scr.h)
        scr.put_center(scr.h // 2 + 1, msg[:scr.w], theme.text_dim, theme.bg)

    def handle(self, ev):
        if getattr(ev, "name", None) == "ctrl-c":
            self.app.running = False
