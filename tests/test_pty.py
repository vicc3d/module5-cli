"""Integration test on a real terminal (pty).

The headless harness verifies the drawing; this verifies the plumbing: raw
mode, the alternate screen, the mouse, redrawing on resize, and -- above all
-- that the terminal is left as it was on exit.

    python3 tests/test_pty.py
"""

import fcntl
import os
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILED = []


def check(label, cond, extra=""):
    print("  [%s] %s%s" % ("ok  " if cond else "FAIL", label,
                           ("  -- " + extra) if extra and not cond else ""))
    if not cond:
        FAILED.append(label)


def set_size(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


TRANSCRIPT = []   # everything the application wrote, in order


def drain(master, seconds=0.6):
    """Reads everything the application has written within the given window.

    What's read also accumulates in TRANSCRIPT: rendering is differential, so
    reconstructing the screen means replaying the whole stream from startup,
    not a loose chunk.
    """
    out = b""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        r, _, _ = select.select([master], [], [], 0.05)
        if not r:
            continue
        try:
            chunk = os.read(master, 65536)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
    text = out.decode("utf-8", "replace")
    TRANSCRIPT.append(text)
    return text


def wait_exit(master, proc, seconds=5):
    """Waits for exit without ever stopping reading the master.

    Reading is required: teardown ends in tcsetattr(TCSADRAIN), which blocks
    until what the application just wrote gets consumed. A real terminal is
    always reading; a test has to imitate that or the game looks like it
    hangs on exit.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        drain(master, 0.1)
        code = proc.poll()
        if code is not None:
            return code
    proc.kill()
    proc.wait()
    return None


def screen_now(rows, cols):
    return render("".join(TRANSCRIPT), rows, cols)


def render(text, rows=30, cols=100):
    """Interprets just enough ANSI to reconstruct what's on screen.

    Supports what the game emits: positioning the cursor, writing, clearing
    the screen, and SGR (which is discarded -- only the characters matter here).
    """
    grid = [[" "] * cols for _ in range(rows)]
    x = y = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\x1b":
            m = re.match(r"\x1b\[([0-9;?]*)([A-Za-z])", text[i:])
            if not m:
                m2 = re.match(r"\x1b\][0-9]*;[^\x07\x1b]*(\x07|\x1b\\)", text[i:])
                i += m2.end() if m2 else 1
                continue
            params, final = m.group(1), m.group(2)
            if final == "H":
                nums = [int(p) for p in params.split(";") if p.isdigit()]
                y = (nums[0] - 1) if len(nums) > 0 else 0
                x = (nums[1] - 1) if len(nums) > 1 else 0
            elif final == "J":
                grid = [[" "] * cols for _ in range(rows)]
                x = y = 0
            i += m.end()
            continue
        if ch == "\r":
            x = 0
        elif ch == "\n":
            y += 1
        elif 0 <= y < rows and 0 <= x < cols:
            grid[y][x] = ch
            x += 1
        else:
            x += 1
        i += 1
    return "\n".join("".join(row).rstrip() for row in grid)


def main():
    rows, cols = 30, 100
    master, slave = pty.openpty()
    set_size(slave, rows, cols)
    env = dict(os.environ)
    env.update({
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "LANG": "es_ES.UTF-8",
        "PYTHONPATH": ROOT,
        "MODULE5_HOME": os.path.join(ROOT, ".test-pty-save"),
    })
    proc = subprocess.Popen(
        [sys.executable, "-m", "m5"],
        stdin=slave, stdout=slave, stderr=slave, env=env, cwd=ROOT,
    )
    os.close(slave)

    print("== arranque en una pty real")
    boot = drain(master, 1.2)
    check("entra en la pantalla alternativa", "\x1b[?1049h" in boot)
    check("esconde el cursor", "\x1b[?25l" in boot)
    check("activa el pegado con corchetes", "\x1b[?2004h" in boot)
    check("activa el mouse (SGR 1006)", "\x1b[?1006h" in boot)
    check("usa color de 24 bits", "38;2;" in boot, boot[:200])
    drain(master, 0.5)   # the first frame can arrive split across two reads
    screen = screen_now(rows, cols)
    # in the menu "MODULE 5" is a block typeface, not text: what's checked
    # is the menu entries and the title drawn with blocks
    check("dibuja el menu",
          all(w in screen for w in ("CLASICO", "FORMAS", "SALIR", "PENTOMINOS")),
          screen[:500])
    check("dibuja el titulo en bloques", screen.count("█") > 40,
          str(screen.count("█")))

    print("\n== jugar")
    os.write(master, b"\r")                  # entra a Clasico
    drain(master, 0.6)
    board = screen_now(rows, cols)
    check("el HUD muestra el tablero", "BANDEJA" in board, board[:600])
    check("el titulo pasa a Clasico", "CLASICO // 6x10" in board, board[:200])
    os.write(master, b"1")                   # toma la pieza F
    os.write(master, b"\x1b[C\x1b[C")        # dos veces a la derecha
    os.write(master, b"r")                   # rotar
    drain(master, 0.5)
    ghost = screen_now(rows, cols)
    check("muestra la pieza en la mano", "PIEZA  F" in ghost, ghost[:900])
    os.write(master, b"\r")                  # colocar
    drain(master, 0.6)
    full = screen_now(rows, cols)
    check("cuenta la pieza colocada", "1/12" in full, full)

    print("\n== cambio de tamano")
    set_size(master, 24, 70)
    proc.send_signal(signal.SIGWINCH)
    resized = drain(master, 0.8)
    check("repinta al recibir SIGWINCH", len(resized) > 100, str(len(resized)))
    small = render(resized, 24, 70)
    check("el juego sigue dibujado tras el resize",
          "BANDEJA" in small or "MODULE 5" in small, small[:400])

    print("\n== terminal muy chica")
    set_size(master, 8, 30)
    proc.send_signal(signal.SIGWINCH)
    tiny = render(drain(master, 0.8), 8, 30)
    check("avisa que la terminal es muy chica", "chica" in tiny or "small" in tiny,
          tiny)

    print("\n== salida limpia")
    set_size(master, 30, 100)
    proc.send_signal(signal.SIGWINCH)
    drain(master, 0.4)
    os.write(master, b"\x03")                # ctrl-c
    code = wait_exit(master, proc)
    tail = "".join(TRANSCRIPT[-6:])
    check("el proceso termina", code == 0, "codigo=%s" % code)
    check("desactiva el mouse", "\x1b[?1006l" in tail or "\x1b[?1000l" in tail, tail[-200:])
    check("desactiva el pegado con corchetes", "\x1b[?2004l" in tail, tail[-200:])
    check("vuelve a mostrar el cursor", "\x1b[?25h" in tail, tail[-200:])
    check("sale de la pantalla alternativa", "\x1b[?1049l" in tail, tail[-200:])
    check("resetea los atributos", "\x1b[0m" in tail, tail[-200:])
    os.close(master)

    print("\n== no es una terminal (tuberia)")
    piped = subprocess.run([sys.executable, "-m", "m5"], cwd=ROOT, env=env,
                           stdin=subprocess.DEVNULL, capture_output=True)
    check("rechaza correr sin terminal", piped.returncode == 2)
    check("y lo explica", b"terminal" in piped.stderr, piped.stderr[:200].decode())

    print("\n" + "=" * 60)
    if FAILED:
        print("FALLARON %d comprobaciones:" % len(FAILED))
        for f in FAILED:
            print("  - " + f)
        return 1
    print("todo en verde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
