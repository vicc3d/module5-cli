"""Terminal engine: raw mode, alternate screen, double-buffered rendering,
and keyboard / mouse input. Standard library only.

curses is deliberately not used: 24-bit color was needed for the game's neon
palette, and a custom diff lets it repaint only what changed (the whole board
is ~250 cells; repainting it fully every tick would flicker over SSH).
Everything emitted is ANSI sequences that any Linux or macOS terminal
understands. No X11, nothing to compile.
"""

import codecs
import os
import re
import select
import signal
import sys
import termios
import tty

# Style attributes

BOLD = 1
DIM = 2
ITALIC = 4
UNDERLINE = 8
REVERSE = 16

# Color detection and conversion

TRUECOLOR, C256, C16, MONO = "truecolor", "256", "16", "mono"


def detect_color_mode():
    if os.environ.get("NO_COLOR"):
        return MONO
    forced = (os.environ.get("MODULE5_COLOR") or "").lower()
    if forced in (TRUECOLOR, C256, C16, MONO):
        return forced
    if (os.environ.get("COLORTERM") or "").lower() in ("truecolor", "24bit"):
        return TRUECOLOR
    term = (os.environ.get("TERM") or "").lower()
    if any(k in term for k in ("kitty", "alacritty", "wezterm", "ghostty", "direct")):
        return TRUECOLOR
    if os.environ.get("TERM_PROGRAM") in ("iTerm.app", "WezTerm", "ghostty", "vscode"):
        return TRUECOLOR
    if "256color" in term:
        return C256
    if term in ("", "dumb"):
        return MONO
    return C16


def rgb(hex_or_tuple):
    """Normalizes '#rrggbb' or (r,g,b) to an 0xRRGGBB integer."""
    if isinstance(hex_or_tuple, int):
        return hex_or_tuple
    if isinstance(hex_or_tuple, tuple):
        r, g, b = hex_or_tuple
        return (r << 16) | (g << 8) | b
    s = hex_or_tuple.lstrip("#")
    return int(s, 16)


def _components(color):
    return (color >> 16) & 255, (color >> 8) & 255, color & 255


def mix(a, b, t):
    """Interpolates two colors (t=0 -> a, t=1 -> b). For dimming and highlighting."""
    ar, ag, ab = _components(rgb(a))
    br, bg, bb = _components(rgb(b))
    return (
        (round(ar + (br - ar) * t) << 16)
        | (round(ag + (bg - ag) * t) << 8)
        | round(ab + (bb - ab) * t)
    )


def _to_256(color):
    r, g, b = _components(color)
    # gray if the three channels are close together
    if abs(r - g) < 12 and abs(g - b) < 12 and abs(r - b) < 12:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + round((r - 8) / 247 * 23)
    q = lambda v: round(v / 255 * 5)
    return 16 + 36 * q(r) + 6 * q(g) + q(b)


_C16_BASE = [
    (0x00, 0x00, 0x00), (0xCD, 0x00, 0x00), (0x00, 0xCD, 0x00), (0xCD, 0xCD, 0x00),
    (0x00, 0x00, 0xEE), (0xCD, 0x00, 0xCD), (0x00, 0xCD, 0xCD), (0xE5, 0xE5, 0xE5),
    (0x7F, 0x7F, 0x7F), (0xFF, 0x00, 0x00), (0x00, 0xFF, 0x00), (0xFF, 0xFF, 0x00),
    (0x5C, 0x5C, 0xFF), (0xFF, 0x00, 0xFF), (0x00, 0xFF, 0xFF), (0xFF, 0xFF, 0xFF),
]


def _to_16(color):
    r, g, b = _components(color)
    best, best_d = 7, None
    for i, (cr, cg, cb) in enumerate(_C16_BASE):
        d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if best_d is None or d < best_d:
            best, best_d = i, d
    return best


class Palette:
    """Translates RGB colors to SGR sequences based on what the terminal supports."""

    def __init__(self, mode):
        self.mode = mode
        self._fg = {}
        self._bg = {}

    @property
    def truecolor(self):
        return self.mode == TRUECOLOR

    @property
    def mono(self):
        return self.mode == MONO

    def fg(self, color):
        if self.mono or color is None:
            return ""
        got = self._fg.get(color)
        if got is None:
            got = self._fg[color] = self._seq(color, False)
        return got

    def bg(self, color):
        if self.mono or color is None:
            return ""
        got = self._bg.get(color)
        if got is None:
            got = self._bg[color] = self._seq(color, True)
        return got

    def _seq(self, color, is_bg):
        if self.mode == TRUECOLOR:
            r, g, b = _components(color)
            return "%d;2;%d;%d;%d" % (48 if is_bg else 38, r, g, b)
        if self.mode == C256:
            return "%d;5;%d" % (48 if is_bg else 38, _to_256(color))
        i = _to_16(color)
        base = (40 if is_bg else 30) + (i & 7)
        return "%d;1" % base if i >= 8 and not is_bg else str(base + (60 if i >= 8 else 0))


# Screen buffer

_BLANK = (" ", None, None, 0)


class Screen:
    """Grid of (char, fg, bg, attr) cells with differential flushing.

    Everything is drawn into `buf`, and `flush()` compares against the
    previous frame to emit only the runs that changed.
    """

    def __init__(self, palette):
        self.pal = palette
        self.w = 0
        self.h = 0
        self.buf = []
        self.prev = []

    def resize(self, w, h):
        if (w, h) == (self.w, self.h):
            return
        self.w, self.h = w, h
        self.buf = [[_BLANK] * w for _ in range(h)]
        self.prev = None  # forces a full repaint
        self.clear()

    def force_redraw(self):
        self.prev = None

    def clear(self, bg=None):
        cell = (" ", None, bg, 0)
        for row in self.buf:
            for x in range(self.w):
                row[x] = cell

    def fill(self, x, y, w, h, ch=" ", fg=None, bg=None, attr=0):
        cell = (ch, fg, bg, attr)
        for yy in range(max(0, y), min(self.h, y + h)):
            row = self.buf[yy]
            for xx in range(max(0, x), min(self.w, x + w)):
                row[xx] = cell

    def put(self, x, y, text, fg=None, bg=None, attr=0, max_w=None):
        """Writes `text` at (x, y), clipping at the edges. Returns the final x."""
        if y < 0 or y >= self.h:
            return x
        limit = self.w if max_w is None else min(self.w, x + max_w)
        row = self.buf[y]
        for ch in text:
            if x >= limit:
                break
            if x >= 0:
                row[x] = (ch, fg, bg, attr)
            x += 1
        return x

    def put_center(self, y, text, fg=None, bg=None, attr=0, x0=0, w=None):
        w = self.w if w is None else w
        return self.put(x0 + max(0, (w - len(text)) // 2), y, text, fg, bg, attr, max_w=w)

    def render(self):
        """Returns the frame's ANSI bytes (differences only)."""
        pal = self.pal
        out = []
        prev = self.prev
        cur_style = None  # (fg, bg, attr) currently active on the terminal
        cur_pos = None    # (x, y) where the cursor ended up

        for y in range(self.h):
            row = self.buf[y]
            prow = prev[y] if prev is not None else None
            x = 0
            while x < self.w:
                if prow is not None and row[x] == prow[x]:
                    x += 1
                    continue
                # a run of differing cells (up to 3 matching ones in a row are
                # tolerated before cutting: repositioning the cursor costs
                # more bytes than rewriting a couple of spaces)
                start = x
                run = []
                same = 0  # matching cells already appended at the run's tail
                while x < self.w:
                    if prow is not None and row[x] == prow[x]:
                        if same >= 3:
                            break
                        same += 1
                    else:
                        same = 0
                    run.append(row[x])
                    x += 1
                if same:
                    # a run always starts on a differing cell, so after
                    # trimming the tail at least one remains and x > start:
                    # the outer loop always makes progress
                    del run[len(run) - same:]
                    x -= same
                if cur_pos != (start, y):
                    out.append("\x1b[%d;%dH" % (y + 1, start + 1))
                for ch, fg, bg, attr in run:
                    style = (fg, bg, attr)
                    if style != cur_style:
                        out.append(_sgr(pal, fg, bg, attr))
                        cur_style = style
                    out.append(ch)
                cur_pos = (start + len(run), y)

        if not out:
            return b""
        # 2026 = "synchronized output": the terminal presents the frame all at
        # once, so no top-to-bottom tearing shows (ignored if unsupported)
        payload = "\x1b[?2026h" + "".join(out) + "\x1b[0m\x1b[?2026l"
        self.prev = [row[:] for row in self.buf]
        return payload.encode("utf-8", "replace")


def _sgr(pal, fg, bg, attr):
    parts = ["0"]
    if attr & BOLD:
        parts.append("1")
    if attr & DIM:
        parts.append("2")
    if attr & ITALIC:
        parts.append("3")
    if attr & UNDERLINE:
        parts.append("4")
    if attr & REVERSE:
        parts.append("7")
    f = pal.fg(fg)
    if f:
        parts.append(f)
    b = pal.bg(bg)
    if b:
        parts.append(b)
    return "\x1b[" + ";".join(parts) + "m"


# Input events

class Key:
    __slots__ = ("name", "char")

    def __init__(self, name, char=None):
        self.name = name
        self.char = char

    def __repr__(self):
        return "Key(%r)" % (self.char or self.name)

    def __eq__(self, other):
        return self.name == other if isinstance(other, str) else NotImplemented

    def __hash__(self):
        return hash(self.name)


class Mouse:
    __slots__ = ("kind", "button", "x", "y")

    def __init__(self, kind, button, x, y):
        self.kind = kind      # 'press' | 'release' | 'drag' | 'wheel'
        self.button = button  # 'left' | 'middle' | 'right' | 'up' | 'down'
        self.x = x
        self.y = y

    def __repr__(self):
        return "Mouse(%s %s %d,%d)" % (self.kind, self.button, self.x, self.y)


class Paste:
    __slots__ = ("text",)

    def __init__(self, text):
        self.text = text


_CSI_KEYS = {
    "A": "up", "B": "down", "C": "right", "D": "left",
    "H": "home", "F": "end", "Z": "shift-tab",
    "1~": "home", "2~": "insert", "3~": "delete", "4~": "end",
    "5~": "pgup", "6~": "pgdn", "7~": "home", "8~": "end",
}

_MOUSE_RE = re.compile(r"\A\x1b\[<(\d+);(\d+);(\d+)([Mm])")
_CSI_RE = re.compile(r"\A\x1b\[([0-9;]*)([A-Za-z~])")
_SS3_RE = re.compile(r"\A\x1bO([A-Za-z])")
_PASTE_RE = re.compile(r"\A\x1b\[200~(.*?)\x1b\[201~", re.S)


class Input:
    """Reads stdin in raw mode and converts it into Key / Mouse / Paste events."""

    def __init__(self, fd):
        self.fd = fd
        self.pending = ""
        # the incremental decoder holds on to multibyte sequences split
        # across two reads (happens when typing accents into a name) and
        # replaces invalid bytes instead of raising
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def _read_available(self, timeout):
        try:
            r, _, _ = select.select([self.fd], [], [], timeout)
        except (OSError, ValueError):
            return False
        if not r:
            return False
        try:
            data = os.read(self.fd, 65536)
        except OSError:
            return False
        if not data:
            return False
        self.pending += self._decoder.decode(data)
        return True

    def poll(self, timeout=0.1):
        """Returns the list of available events (may be empty)."""
        self._read_available(timeout)
        events = []
        while self.pending:
            ev, consumed = self._parse()
            if consumed == 0:
                # incomplete sequence: wait a bit longer for the rest
                if self._read_available(0.02):
                    continue
                if self.pending == "\x1b":
                    self.pending = ""
                    events.append(Key("esc"))
                else:
                    # unrecognizable garbage: discard the first byte
                    self.pending = self.pending[1:]
                continue
            self.pending = self.pending[consumed:]
            if ev is not None:
                events.append(ev)
        return events

    def _parse(self):
        s = self.pending
        ch = s[0]

        if ch == "\x1b":
            if len(s) == 1:
                return None, 0  # could be a lone ESC or the start of a sequence
            m = _PASTE_RE.match(s)
            if m:
                return Paste(m.group(1)), m.end()
            if s.startswith("\x1b[200~"):
                return None, 0  # incomplete paste: wait for the closing tag
            m = _MOUSE_RE.match(s)
            if m:
                return _parse_mouse(m), m.end()
            if s.startswith("\x1b[<"):
                return None, 0
            m = _CSI_RE.match(s)
            if m:
                params, final = m.group(1), m.group(2)
                name = _CSI_KEYS.get(final) or _CSI_KEYS.get(params + final)
                if name is None and final == "~":
                    name = _CSI_KEYS.get(params.split(";")[0] + "~")
                return (Key(name) if name else None), m.end()
            if s.startswith("\x1b["):
                return None, 0
            m = _SS3_RE.match(s)
            if m:
                name = _CSI_KEYS.get(m.group(1))
                return (Key(name) if name else None), m.end()
            if s.startswith("\x1bO"):
                return None, 0
            # ESC + key = alt-<key>; treated as a lone ESC
            return Key("esc"), 1

        if ch in ("\r", "\n"):
            return Key("enter"), 1
        if ch == "\t":
            return Key("tab"), 1
        if ch in ("\x7f", "\x08"):
            return Key("backspace"), 1
        if ch == " ":
            return Key("space", " "), 1
        if ch < " ":
            code = ord(ch)
            return Key("ctrl-" + chr(code + 96)), 1
        return Key("char", ch), 1


def _parse_mouse(m):
    code, x, y, final = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    if code & 64:
        return Mouse("wheel", "up" if (code & 3) == 0 else "down", x - 1, y - 1)
    button = ("left", "middle", "right", "none")[code & 3]
    if final == "m":
        kind = "release"
    elif code & 32:
        kind = "drag"
    else:
        kind = "press"
    return Mouse(kind, button, x - 1, y - 1)


# The terminal itself

class Terminal:
    """Context manager: enters raw mode + the alternate screen and restores
    everything on exit (even if the game crashes, or gets suspended with ^Z)."""

    def __init__(self, mouse=True):
        self.in_fd = sys.stdin.fileno()
        self.out_fd = sys.stdout.fileno()
        self.saved = None
        self.want_mouse = mouse
        self.pal = Palette(detect_color_mode())
        self.screen = Screen(self.pal)
        self.input = Input(self.in_fd)
        self.resized = True
        self._entered = False

    # Lifecycle

    def __enter__(self):
        self._setup()
        signal.signal(signal.SIGWINCH, self._on_winch)
        if hasattr(signal, "SIGCONT"):
            signal.signal(signal.SIGCONT, self._on_cont)
        if hasattr(signal, "SIGTSTP"):
            signal.signal(signal.SIGTSTP, self._on_tstp)
        return self

    def __exit__(self, *exc):
        self._teardown()
        return False

    def _setup(self):
        self.saved = termios.tcgetattr(self.in_fd)
        tty.setraw(self.in_fd)
        seq = "\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H\x1b[?2004h"
        if self.want_mouse:
            seq += "\x1b[?1000h\x1b[?1002h\x1b[?1006h"
        self.write(seq)
        self._entered = True
        self.screen.force_redraw()

    def _teardown(self):
        if not self._entered:
            return
        seq = "\x1b[?2004l"
        if self.want_mouse:
            seq += "\x1b[?1006l\x1b[?1002l\x1b[?1000l"
        seq += "\x1b[0m\x1b[?25h\x1b[?1049l"
        self.write(seq)
        if self.saved is not None:
            try:
                termios.tcsetattr(self.in_fd, termios.TCSADRAIN, self.saved)
            except termios.error:
                pass
        self._entered = False

    def _on_winch(self, *_):
        self.resized = True

    def _on_cont(self, *_):
        # coming back from a ^Z requires redoing raw mode + alternate screen
        self._setup()
        self.resized = True

    def _on_tstp(self, *_):
        self._teardown()
        signal.signal(signal.SIGTSTP, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTSTP)
        signal.signal(signal.SIGTSTP, self._on_tstp)

    # Output

    def write(self, text):
        data = text.encode("utf-8", "replace") if isinstance(text, str) else text
        while data:
            try:
                n = os.write(self.out_fd, data)
            except (BlockingIOError, InterruptedError):
                continue
            except OSError:
                return
            data = data[n:]

    def size(self):
        try:
            cols, rows = os.get_terminal_size(self.out_fd)
        except OSError:
            cols, rows = 80, 24
        return max(1, cols), max(1, rows)

    def sync_size(self):
        """Adjusts the buffer to the current size. True if it changed."""
        w, h = self.size()
        changed = (w, h) != (self.screen.w, self.screen.h)
        self.screen.resize(w, h)
        self.resized = False
        return changed

    def present(self):
        self.write(self.screen.render())

    # Input

    def poll(self, timeout=0.1):
        return self.input.poll(timeout)

    # Clipboard

    def copy(self, text):
        """Copies to the clipboard. Returns True if some method worked.

        OSC 52 is tried first, since it's an escape sequence and so works
        without X11 and even over SSH; then the system tools, in case the
        terminal has it disabled.
        """
        import base64 as _b64
        import shutil
        import subprocess

        ok = False
        try:
            payload = _b64.b64encode(text.encode("utf-8")).decode("ascii")
            self.write("\x1b]52;c;%s\x07" % payload)
            ok = True
        except OSError:
            pass
        for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-ib"]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, input=text.encode("utf-8"), check=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except (OSError, subprocess.CalledProcessError):
                    continue
        return ok
