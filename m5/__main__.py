"""Entry point: python3 -m m5 (or the ./module5 launcher)."""

import argparse
import os
import sys

from . import __version__


def build_parser():
    p = argparse.ArgumentParser(
        prog="module5",
        description="Module 5 - pentominoes in the terminal (zero dependencies).",
    )
    p.add_argument("--version", action="version", version="Module 5 " + __version__)
    p.add_argument("--lang", choices=("es", "en"), help="language (default: system's)")
    p.add_argument("--theme", choices=("neon", "ascii", "blueprint", "mono"),
                   help="visual theme")
    p.add_argument("--ascii", action="store_true",
                   help="use ASCII-only glyphs (for plain terminals)")
    p.add_argument("--no-mouse", action="store_true", help="don't enable the mouse")
    p.add_argument("--no-color", action="store_true", help="no color")
    p.add_argument("--save-dir", metavar="DIR",
                   help="folder for the save file (default: the system's)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.no_color:
        os.environ["NO_COLOR"] = "1"
    if args.save_dir:
        os.environ["MODULE5_HOME"] = args.save_dir

    if not sys.stdout.isatty():
        sys.stderr.write(
            "module5: stdout is not an interactive terminal.\n"
            "Run it directly in your terminal (not through a pipe).\n")
        return 2
    if not sys.stdin.isatty():
        sys.stderr.write("module5: a keyboard is needed (stdin is not a terminal).\n")
        return 2

    # the game draws its own glyphs; --ascii and the autodetected choice are
    # resolved before importing anything that uses them
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
