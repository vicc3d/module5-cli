"""Drawing primitives: frames, the board, the tray, silhouettes, and a text
field. Everything paints onto the Screen buffer; nothing writes to the
terminal directly.
"""

from .glyphs import g
from .pieces import PIECE_KEYS, PIECE_NAMES
from .term import BOLD, DIM, REVERSE, UNDERLINE

# A terminal character is roughly twice as tall as it is wide, so a square
# cell needs twice as many columns as rows. These are the possible scales,
# smallest to largest: the board picks the largest one that fits the
# terminal, instead of always staying at the smallest.
CELL_SCALES = ((2, 1), (4, 2), (6, 3), (8, 4))
CELL_W = 2  # minimum scale, used to measure whether the side panel fits


def board_size(board, scale=(2, 1)):
    """Width and height in characters of the board with its frame."""
    cw, ch = scale
    return board.cols * cw + 3, board.rows * ch + 2


def max_scale_index(board, avail_w, avail_h):
    """The index of the largest cell that still fits the area."""
    best = 0
    for i, scale in enumerate(CELL_SCALES):
        w, h = board_size(board, scale)
        if w <= avail_w and h <= avail_h:
            best = i
    return best


def auto_scale_index(board, avail_w, avail_h):
    """The scale the game picks on its own, without manual zoom.

    The ceiling depends on how many cells the silhouette has: stretching a
    large board too much spaces the letters out enough that pieces stop
    reading as a single shape, while a small silhouette (the early levels)
    would get lost in the middle of the screen if it isn't enlarged.
    """
    limit = 8 if len(board.cells) <= 25 else 4
    top = max_scale_index(board, avail_w, avail_h)
    while top > 0 and CELL_SCALES[top][0] > limit:
        top -= 1
    return top


def resolve_scale(board, avail_w, avail_h, zoom=None):
    """Returns (scale, index, max_index, auto_index).

    `zoom` is a manually chosen index; it's clamped to what fits on screen, so
    zooming in too far never overflows the board. With zoom None, the
    automatic scale rules.
    """
    top = max_scale_index(board, avail_w, avail_h)
    auto = auto_scale_index(board, avail_w, avail_h)
    idx = auto if zoom is None else min(max(int(zoom), 0), top)
    return CELL_SCALES[idx], idx, top, auto


def pick_scale(board, avail_w, avail_h, zoom=None):
    return resolve_scale(board, avail_w, avail_h, zoom)[0]


def draw_cell(scr, x, y, cw, ch, glyph, fg, bg, attr=0, body=" ", body_fg=None):
    """Paints a cw x ch cell with its glyph centered.

    At the minimum scale (2x1) the cell *is* the glyph; from there on the
    block gets filled in and the letter stays centered inside it.
    """
    for yy in range(ch):
        scr.put(x, y + yy, body * cw, body_fg if body_fg is not None else fg, bg, attr)
    if glyph and glyph != " ":
        scr.put(x + (cw - 1) // 2, y + (ch - 1) // 2, glyph, fg, bg, attr)


def scrim(scr, theme, amount=0.72):
    """Dims everything already drawn so a modal on top stands out.

    Without this the game's side panel still reads next to the modal and it
    looks like the text is spilling out of the box.
    """
    from .term import mix

    bg = theme.bg
    if bg is None:
        # colorless theme: the only thing available is the dim attribute
        for y in range(scr.h):
            row = scr.buf[y]
            for x in range(scr.w):
                ch, fg, cbg, attr = row[x]
                if not (attr & DIM):
                    row[x] = (ch, fg, cbg, attr | DIM)
        return
    memo = {}

    def faded(color):
        if color is None:
            return None
        got = memo.get(color)
        if got is None:
            got = memo[color] = mix(color, bg, amount)
        return got

    for y in range(scr.h):
        row = scr.buf[y]
        for x in range(scr.w):
            ch, fg, cbg, attr = row[x]
            if ch == " " and cbg is None:
                continue
            row[x] = (ch, faded(fg), faded(cbg), attr & ~BOLD)


def box(scr, x, y, w, h, theme, title=None, double=False, color=None, title_color=None, fill=True):
    """Frame with an optional title embedded in the top border."""
    if w < 2 or h < 2:
        return
    color = theme.border if color is None else color
    tl, tr, bl, br = (g("dtl"), g("dtr"), g("dbl"), g("dbr")) if double else (g("tl"), g("tr"), g("bl"), g("br"))
    hz, vt = (g("dh"), g("dv")) if double else (g("h"), g("v"))
    bg = theme.panel if fill else None
    if fill:
        scr.fill(x, y, w, h, " ", theme.text, bg)
    scr.put(x, y, tl + hz * (w - 2) + tr, color, bg)
    for yy in range(y + 1, y + h - 1):
        scr.put(x, yy, vt, color, bg)
        scr.put(x + w - 1, yy, vt, color, bg)
    scr.put(x, y + h - 1, bl + hz * (w - 2) + br, color, bg)
    if title:
        label = " %s " % title
        if len(label) <= w - 4:
            scr.put(x + 2, y, label, title_color or theme.text_hi, bg, BOLD)


def draw_board(scr, x, y, game, theme, ghost=None, show_cursor=True, scale=(2, 1)):
    """The board with a double frame, placed pieces, and the ghost piece."""
    board = game.board
    cw, chh = scale
    inner = board.cols * cw + 1
    bg = theme.board_bg
    scr.put(x, y, g("dtl") + g("dh") * inner + g("dtr"), theme.border, bg)
    scr.put(x, y + board.rows * chh + 1,
            g("dbl") + g("dh") * inner + g("dbr"), theme.border, bg)

    ghost_cells = {}
    if ghost:
        for cell in ghost.cells:
            ghost_cells[cell] = ghost.valid

    for r in range(board.rows):
        for sub in range(chh):
            yy = y + 1 + r * chh + sub
            scr.put(x, yy, g("dv"), theme.border, bg)
            scr.put(x + inner + 1, yy, g("dv"), theme.border, bg)
            scr.put(x + 1, yy, " ", theme.text, bg)
        for c in range(board.cols):
            cx = x + 2 + c * cw
            cy = y + 1 + r * chh
            glyph, fg, cbg, attr, body, body_fg = _cell_style(
                game, theme, r, c, ghost_cells, scale)
            if show_cursor and game.cursor == (r, c) and not ghost:
                # without a piece in hand the cursor has to stand out on its own
                attr |= REVERSE
            draw_cell(scr, cx, cy, cw, chh, glyph, fg, cbg, attr, body, body_fg)


def _cell_style(game, theme, r, c, ghost_cells, scale=(2, 1)):
    """Returns (glyph, fg, bg, attr, body, body_color) for a cell.

    At the minimum scale the glyph fills the cell; at larger ones there's room
    for a body (the colored tile, or a block in the text-based themes) with
    the piece's letter centered on top.
    """
    cell = (r, c)
    bg = theme.board_bg
    big = scale[0] > 2
    # in themes without tiles the piece's body is a block; in tiled themes
    # the background color already serves as the body
    solid = g("full") if big else " "

    if cell in ghost_cells:
        valid = ghost_cells[cell]
        name = game.sel["name"]
        if not valid:
            return g("bad"), theme.bad, bg, BOLD, " ", None
        if theme.tiles:
            return (name, theme.piece(name), theme.dim_piece(name, 0.55), BOLD,
                    " ", None)
        return (name, theme.piece(name), bg, DIM | BOLD, solid,
                theme.dim_piece(name, 0.5))
    owner = game.occupied.get(cell)
    if owner:
        if theme.tiles:
            return owner, theme.tile_text, theme.piece(owner), BOLD, " ", None
        return (owner, theme.piece(owner), bg, BOLD, solid,
                theme.dim_piece(owner, 0.35))
    if cell in game.target:
        return g("empty_cell"), theme.empty, bg, 0, " ", None
    return " ", theme.text_dim, bg, 0, " ", None


def draw_tray(scr, x, y, w, game, theme):
    """The tray: the 12 pieces with their key, dimmed if already placed."""
    items = []
    for name in PIECE_NAMES:
        key = PIECE_KEYS[name]
        placed = name in game.placed
        selected = game.sel and game.sel["name"] == name
        items.append((name, key, placed, selected))

    # each entry is 2 columns (key + letter) plus 2 of spacing
    cx = x
    for name, key, placed, selected in items:
        if cx + 2 > x + w:
            break
        if placed:
            key_fg, key_bg, key_at = theme.text_dim, theme.panel, DIM
            name_fg, name_bg, name_at = theme.text_dim, theme.panel, DIM
        elif selected and theme.tiles:
            # the piece in hand shows as a tile, just like on the board
            key_fg, key_bg, key_at = theme.tile_text, theme.piece(name), BOLD
            name_fg, name_bg, name_at = theme.tile_text, theme.piece(name), BOLD
        elif selected:
            key_fg, key_bg, key_at = theme.piece(name), theme.panel, BOLD | REVERSE
            name_fg, name_bg, name_at = theme.piece(name), theme.panel, BOLD | REVERSE
        else:
            key_fg, key_bg, key_at = theme.text_dim, theme.panel, 0
            name_fg, name_bg, name_at = theme.piece(name), theme.panel, BOLD
        scr.put(cx, y, key, key_fg, key_bg, key_at)
        scr.put(cx + 1, y, name, name_fg, name_bg, name_at)
        cx += 4
    return cx


def draw_minimap(scr, x, y, board, theme, occupied):
    """A small, non-interactive copy of the board: same 2-char cells, same
    piece colors and letters as the real one, filling in live as pieces
    land -- the terminal's answer to the web version's #preview canvas.
    """
    target = {tuple(c) for c in board.cells}
    for r in range(board.rows):
        for c in range(board.cols):
            cell = (r, c)
            if cell not in target:
                continue
            cx = x + c * CELL_W
            cy = y + r
            owner = occupied.get(cell)
            if owner:
                if theme.tiles:
                    draw_cell(scr, cx, cy, CELL_W, 1, owner, theme.tile_text,
                              theme.piece(owner), BOLD)
                else:
                    draw_cell(scr, cx, cy, CELL_W, 1, owner, theme.piece(owner),
                              theme.panel, BOLD, body=g("full"),
                              body_fg=theme.dim_piece(owner, 0.35))
            else:
                draw_cell(scr, cx, cy, CELL_W, 1, g("empty_cell"), theme.empty,
                          theme.panel)
    return board.rows


def hint(scr, x, y, w, pairs, theme):
    """Help line: (key, action) pairs separated by a dot."""
    cx = x
    sep = g("sep")
    for i, (key, action) in enumerate(pairs):
        piece = ("%s %s" % (key, action))
        need = len(piece) + (len(sep) if i else 0)
        if cx + need > x + w:
            break
        if i:
            scr.put(cx, y, sep, theme.text_dim, theme.panel)
            cx += len(sep)
        cx = scr.put(cx, y, key, theme.accent, theme.panel, BOLD)
        cx = scr.put(cx, y, " " + action, theme.text_dim, theme.panel)
    return cx


def wrap(text, width):
    """Word-based line wrapping (the game's texts are short)."""
    words, lines, cur = text.split(), [], ""
    for word in words:
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class TextField:
    """A single-line text field, with cursor and horizontal scrolling.

    Used for a challenge's name and for pasting "M5.…" codes, which are
    longer than the visible width.
    """

    def __init__(self, value="", max_len=200):
        self.value = value
        self.max_len = max_len
        self.pos = len(value)
        self.scroll = 0

    def handle(self, ev):
        """Processes an event. True if it consumed it."""
        name = getattr(ev, "name", None)
        if name == "char":
            self.insert(ev.char)
            return True
        if name == "space":
            self.insert(" ")
            return True
        if name == "backspace":
            if self.pos > 0:
                self.value = self.value[:self.pos - 1] + self.value[self.pos:]
                self.pos -= 1
            return True
        if name == "delete":
            self.value = self.value[:self.pos] + self.value[self.pos + 1:]
            return True
        if name == "left":
            self.pos = max(0, self.pos - 1)
            return True
        if name == "right":
            self.pos = min(len(self.value), self.pos + 1)
            return True
        if name == "home":
            self.pos = 0
            return True
        if name == "end":
            self.pos = len(self.value)
            return True
        if name == "ctrl-u":
            self.value, self.pos = "", 0
            return True
        if name == "ctrl-w":
            left = self.value[:self.pos].rstrip()
            cut = left.rfind(" ") + 1
            self.value = self.value[:cut] + self.value[self.pos:]
            self.pos = cut
            return True
        if hasattr(ev, "text"):  # paste
            self.insert(ev.text.replace("\n", "").replace("\r", ""))
            return True
        return False

    def insert(self, text):
        room = self.max_len - len(self.value)
        if room <= 0:
            return
        text = text[:room]
        self.value = self.value[:self.pos] + text + self.value[self.pos:]
        self.pos += len(text)

    def draw(self, scr, x, y, w, theme, focus=True):
        # keep the cursor in view
        if self.pos < self.scroll:
            self.scroll = self.pos
        elif self.pos >= self.scroll + w - 1:
            self.scroll = self.pos - w + 2
        self.scroll = max(0, min(self.scroll, max(0, len(self.value) - w + 1)))
        visible = self.value[self.scroll:self.scroll + w]
        scr.fill(x, y, w, 1, " ", theme.text, theme.bg)
        scr.put(x, y, visible, theme.text_hi, theme.bg)
        if focus:
            cx = x + self.pos - self.scroll
            ch = self.value[self.pos] if self.pos < len(self.value) else " "
            scr.put(cx, y, ch, theme.text_hi, theme.bg, REVERSE)
        if self.scroll > 0:
            scr.put(x, y, g("left"), theme.accent, theme.bg, BOLD)
        if self.scroll + w < len(self.value):
            scr.put(x + w - 1, y, g("right"), theme.accent, theme.bg, BOLD)
