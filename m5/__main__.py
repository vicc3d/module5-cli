"""Punto de entrada: python3 -m m5 (o el lanzador ./module5)."""

import argparse
import os
import sys

from . import __version__


def build_parser():
    p = argparse.ArgumentParser(
        prog="module5",
        description="Module 5 - pentominos en la terminal (sin dependencias).",
    )
    p.add_argument("--version", action="version", version="Module 5 " + __version__)
    p.add_argument("--lang", choices=("es", "en"), help="idioma (por defecto: el del sistema)")
    p.add_argument("--theme", choices=("neon", "ascii", "blueprint", "mono"),
                   help="tema visual")
    p.add_argument("--ascii", action="store_true",
                   help="usar solo caracteres ASCII (para terminales sobrias)")
    p.add_argument("--no-mouse", action="store_true", help="no activar el mouse")
    p.add_argument("--no-color", action="store_true", help="sin color")
    p.add_argument("--save-dir", metavar="DIR",
                   help="carpeta del archivo de progreso (por defecto la del sistema)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.no_color:
        os.environ["NO_COLOR"] = "1"
    if args.save_dir:
        os.environ["MODULE5_HOME"] = args.save_dir

    if not sys.stdout.isatty():
        sys.stderr.write(
            "module5: la salida no es una terminal interactiva.\n"
            "Ejecutalo directamente en tu terminal (no por una tuberia).\n")
        return 2
    if not sys.stdin.isatty():
        sys.stderr.write("module5: se necesita un teclado (stdin no es una terminal).\n")
        return 2

    # el juego dibuja sus propios glifos; --ascii y el autodetectado se
    # resuelven antes de importar cualquier cosa que los use
    from . import glyphs
    if args.ascii:
        glyphs.use_ascii(True)

    from .app import App
    from .store import Store
    from .term import Terminal

    store = Store()
    if args.lang:
        store.settings["lang"] = args.lang
    if args.theme:
        store.settings["theme"] = args.theme

    use_mouse = store.settings.get("mouse", True) and not args.no_mouse
    with Terminal(mouse=use_mouse) as term:
        app = App(term, store)
        try:
            app.run()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
