"""Test harness: runs the whole application without a real terminal.

Substitutes Terminal with a double that keeps the same Screen buffer but
doesn't write to any descriptor, so keys can be injected and the screen read
back as plain text.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from m5.app import App                                    # noqa: E402
from m5.pieces import ORIENTATIONS, centroid_of, normalize_cells  # noqa: E402
from m5.solver import solve                               # noqa: E402
from m5.store import Store                                # noqa: E402
from m5.term import Key, Mouse, Palette, Paste, Screen    # noqa: E402


class FakeTerminal:
    def __init__(self, w=100, h=30, color_mode="truecolor"):
        self.pal = Palette(color_mode)
        self.screen = Screen(self.pal)
        self.screen.resize(w, h)
        self.resized = False
        self.frames = 0
        self.copied = []
        self._w, self._h = w, h

    def sync_size(self):
        self.screen.resize(self._w, self._h)
        self.resized = False
        return True

    def resize(self, w, h):
        self._w, self._h = w, h
        self.resized = True

    def present(self):
        # actually rendered: this way tests catch a crash in the sequence
        # generator, not just in the drawing
        self.screen.render()
        self.frames += 1

    def poll(self, timeout=0.1):
        return []

    def copy(self, text):
        self.copied.append(text)
        return True

    def write(self, data):
        pass


class Harness:
    def __init__(self, w=100, h=30, color_mode="truecolor", theme="neon", lang="es",
                 settings=None, home=None):
        # `home` reuses another instance's directory: useful for testing that
        # what's saved survives a restart
        self.tmp = home or tempfile.mkdtemp(prefix="module5-test-")
        os.environ["MODULE5_HOME"] = self.tmp
        store = Store()
        store.settings["theme"] = theme
        store.settings["lang"] = lang
        if settings:
            store.settings.update(settings)
        self.term = FakeTerminal(w, h, color_mode)
        self.app = App(self.term, store)

    # Input

    def key(self, name, char=None):
        self.app.dispatch(Key(name, char))
        self.render()
        return self

    def type(self, text):
        for ch in text:
            self.app.dispatch(Key("space" if ch == " " else "char", ch))
        self.render()
        return self

    def paste(self, text):
        self.app.dispatch(Paste(text))
        self.render()
        return self

    def mouse(self, kind, button, x, y):
        self.app.dispatch(Mouse(kind, button, x, y))
        self.render()
        return self

    def keys(self, *names):
        for n in names:
            if len(n) == 1 and n not in ("\t",):
                self.key("char", n)
            else:
                self.key(n)
        return self

    def render(self):
        self.app.render_once()
        return self

    # Reading

    def lines(self):
        scr = self.term.screen
        return ["".join(cell[0] for cell in row).rstrip() for row in scr.buf]

    def text(self):
        return "\n".join(self.lines())

    def show(self, label=""):
        bar = "-" * self.term.screen.w
        print("%s\n%s (%dx%d)\n%s" % (bar, label, self.term.screen.w,
                                      self.term.screen.h, bar))
        print(self.text())
        print(bar)
        return self

    def has(self, needle):
        return needle in self.text()

    @property
    def top(self):
        return self.app.top.__class__.__name__

    @property
    def game(self):
        return self.app.game

    @property
    def store(self):
        return self.app.store


def auto_solve(harness):
    """Solves the current board by placing pieces one by one through the
    real game path (select, orient, move the cursor, place)."""
    app = harness.app
    gm = app.game
    cell_list = [tuple(c) for c in gm.board.cells]
    placements, timed_out = solve(cell_list, time_limit=30)
    assert placements, "the test board should be solvable"
    screen = app.top
    for name, mask in placements:
        cells = [cell_list[i] for i in range(len(cell_list)) if (mask >> i) & 1]
        target = normalize_cells(cells)
        assert gm.select(name), "could not select %s" % name
        for ori in ORIENTATIONS[name]:
            if ori == target:
                gm.sel["orient"] = ori
                break
        else:
            raise AssertionError("orientation not found for %s" % name)
        anchor_r = min(c[0] for c in cells)
        anchor_c = min(c[1] for c in cells)
        cr, cc = centroid_of(gm.sel["orient"])
        gm.cursor = (anchor_r + cr, anchor_c + cc)
        screen.try_place()
    harness.render()   # so the buffer reflects the victory modal
    return placements
