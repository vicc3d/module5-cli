"""Primitivas de dibujo: marcos, el tablero, la bandeja, siluetas y un campo
de texto. Todo se pinta sobre el buffer de Screen; nada escribe a la terminal
directamente.
"""

from .glyphs import g
from .pieces import PIECE_KEYS, PIECE_NAMES, bounds_of
from .term import BOLD, DIM, REVERSE, UNDERLINE

# Un caracter de terminal mide aproximadamente el doble de alto que de ancho,
# asi que una celda cuadrada necesita el doble de columnas que de filas. Estas
# son las escalas posibles, de menor a mayor: el tablero elige la mas grande
# que entre en la terminal, en vez de quedarse siempre en la mas chica.
CELL_SCALES = ((2, 1), (4, 2), (6, 3), (8, 4))
CELL_W = 2  # escala minima, la que se usa para medir si el panel lateral cabe


def board_size(board, scale=(2, 1)):
    """Ancho y alto en caracteres del tablero con su marco."""
    cw, ch = scale
    return board.cols * cw + 3, board.rows * ch + 2


def max_scale_index(board, avail_w, avail_h):
    """El indice de la celda mas grande que todavia entra en el area."""
    best = 0
    for i, scale in enumerate(CELL_SCALES):
        w, h = board_size(board, scale)
        if w <= avail_w and h <= avail_h:
            best = i
    return best


def auto_scale_index(board, avail_w, avail_h):
    """La escala que el juego elige solo, sin zoom manual.

    El tope depende de cuantas celdas tenga la silueta: estirar mucho un
    tablero grande separa tanto las letras que las piezas dejan de leerse como
    una sola figura, mientras que una silueta chica (los primeros niveles)
    quedaria perdida en el medio de la pantalla si no se agranda.
    """
    limit = 8 if len(board.cells) <= 25 else 4
    top = max_scale_index(board, avail_w, avail_h)
    while top > 0 and CELL_SCALES[top][0] > limit:
        top -= 1
    return top


def resolve_scale(board, avail_w, avail_h, zoom=None):
    """Devuelve (escala, indice, indice_maximo, indice_automatico).

    `zoom` es un indice elegido a mano; se recorta a lo que entre en pantalla,
    asi que acercarse de mas nunca desborda el tablero. Con zoom None manda la
    escala automatica.
    """
    top = max_scale_index(board, avail_w, avail_h)
    auto = auto_scale_index(board, avail_w, avail_h)
    idx = auto if zoom is None else min(max(int(zoom), 0), top)
    return CELL_SCALES[idx], idx, top, auto


def pick_scale(board, avail_w, avail_h, zoom=None):
    return resolve_scale(board, avail_w, avail_h, zoom)[0]


def draw_cell(scr, x, y, cw, ch, glyph, fg, bg, attr=0, body=" ", body_fg=None):
    """Pinta una celda de cw x ch caracteres con su glifo al centro.

    Con la escala minima (2x1) la celda *es* el glifo; a partir de ahi se
    rellena el bloque y la letra queda centrada dentro.
    """
    for yy in range(ch):
        scr.put(x, y + yy, body * cw, body_fg if body_fg is not None else fg, bg, attr)
    if glyph and glyph != " ":
        scr.put(x + (cw - 1) // 2, y + (ch - 1) // 2, glyph, fg, bg, attr)


def scrim(scr, theme, amount=0.72):
    """Apaga todo lo ya dibujado para que un modal encima destaque.

    Sin esto el panel lateral del juego se sigue leyendo al costado del modal
    y parece que el texto se saliera de la caja.
    """
    from .term import mix

    bg = theme.bg
    if bg is None:
        # tema sin color: lo unico disponible es el atributo de atenuado
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
    """Marco con titulo opcional incrustado en el borde superior."""
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
    """El tablero con marco doble, las piezas colocadas y el fantasma."""
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
                # sin pieza en la mano el cursor tiene que verse solo
                attr |= REVERSE
            draw_cell(scr, cx, cy, cw, chh, glyph, fg, cbg, attr, body, body_fg)


def _cell_style(game, theme, r, c, ghost_cells, scale=(2, 1)):
    """Devuelve (glifo, fg, bg, attr, relleno, color_relleno) de una celda.

    Con la escala minima el glifo llena la celda; en las grandes hay lugar para
    un cuerpo (la baldosa de color, o un bloque en los temas de texto) con la
    letra de la pieza centrada encima.
    """
    cell = (r, c)
    bg = theme.board_bg
    big = scale[0] > 2
    # en los temas sin baldosas el cuerpo de la pieza es un bloque; en los
    # de baldosas el color de fondo ya hace de cuerpo
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
    """La bandeja: las 12 piezas con su tecla, apagadas si ya estan puestas."""
    items = []
    for name in PIECE_NAMES:
        key = PIECE_KEYS[name]
        placed = name in game.placed
        selected = game.sel and game.sel["name"] == name
        items.append((name, key, placed, selected))

    # cada entrada son 2 columnas (tecla + letra) mas 2 de separacion
    cx = x
    for name, key, placed, selected in items:
        if cx + 2 > x + w:
            break
        if placed:
            key_fg, key_bg, key_at = theme.text_dim, theme.panel, DIM
            name_fg, name_bg, name_at = theme.text_dim, theme.panel, DIM
        elif selected and theme.tiles:
            # la pieza en la mano se muestra como baldosa, igual que en el tablero
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


def draw_piece_shape(scr, x, y, cells, color, theme, fill_bg=True):
    """Miniatura de una pieza (2 columnas por celda), para el panel lateral."""
    rows, cols = bounds_of(cells)
    cellset = set(cells)
    for r in range(rows):
        for c in range(cols):
            cx = x + c * CELL_W
            if (r, c) in cellset:
                if theme.tiles and fill_bg:
                    scr.put(cx, y + r, "  ", theme.tile_text, color)
                else:
                    scr.put(cx, y + r, g("full") * CELL_W, color, theme.panel)
    return rows


def draw_silhouette(scr, x, y, board, theme, occupied=None):
    """Silueta objetivo comprimida: cada linea de texto son dos filas del
    tablero (medios bloques), asi un 6x10 entra en 10x3 caracteres."""
    cells = {tuple(c) for c in board.cells}
    done = set(occupied or ())
    lines = (board.rows + 1) // 2
    for i in range(lines):
        r_top, r_bot = i * 2, i * 2 + 1
        for c in range(board.cols):
            top = (r_top, c) in cells
            bot = (r_bot, c) in cells and r_bot < board.rows
            if top and bot:
                ch = g("full")
            elif top:
                ch = g("upper")
            elif bot:
                ch = g("lower")
            else:
                ch = " "
            if ch == " ":
                continue
            # si se pasa `occupied`, lo ya resuelto se pinta al maximo brillo
            filled = ((r_top, c) in done) or ((r_bot, c) in done)
            color = theme.accent if filled else theme.text_dim
            scr.put(x + c, y + i, ch, color, theme.panel)
    return lines


def hint(scr, x, y, w, pairs, theme):
    """Linea de ayuda: pares (tecla, accion) separados por un punto."""
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
    """Corte de lineas por palabras (los textos del juego son cortos)."""
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
    """Campo de texto de una linea, con cursor y desplazamiento horizontal.

    Se usa para el nombre de un desafio y para pegar codigos "M5.…", que son
    mas largos que el ancho visible.
    """

    def __init__(self, value="", max_len=200):
        self.value = value
        self.max_len = max_len
        self.pos = len(value)
        self.scroll = 0

    def handle(self, ev):
        """Procesa un evento. True si lo consumio."""
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
        if hasattr(ev, "text"):  # pegado
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
        # mantener el cursor a la vista
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
