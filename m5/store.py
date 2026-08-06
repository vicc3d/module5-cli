"""Persistencia en disco y codigos de intercambio de desafios.

La version web guardaba en localStorage; aca se usa un unico JSON en el
directorio de datos del usuario (XDG en Linux, Application Support en macOS).
El formato de los codigos "M5.…" es identico al de la web, asi que un desafio
creado en la terminal se puede importar en el navegador y al reves.
"""

import base64
import json
import os
import sys
import time

from .i18n import detect_lang, t

APP = "module5"
SCHEMA = 1

DEFAULT_SETTINGS = {
    "lang": None,      # None = detectar del entorno en el primer arranque
    "theme": "neon",
    "mouse": True,
}

DEFAULTS = {
    "schema": SCHEMA,
    "solutions": [],     # soluciones canonicas del modo clasico
    "classic_best": None,
    "levels": {},        # "index" -> {"best": ms}
    "slots": {},         # "0".."4" -> snapshot
    "custom": [],        # desafios propios
    "settings": dict(DEFAULT_SETTINGS),
}


def data_dir():
    if os.environ.get("MODULE5_HOME"):
        return os.path.expanduser(os.environ["MODULE5_HOME"])
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/" + APP)
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP)


def save_path():
    return os.path.join(data_dir(), "save.json")


class Store:
    """El archivo de progreso, cargado en memoria y escrito de forma atomica."""

    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULTS))
        self.load()

    def load(self):
        try:
            with open(save_path(), encoding="utf-8") as fh:
                disk = json.load(fh)
        except (OSError, ValueError):
            disk = {}
        if isinstance(disk, dict):
            for key, default in DEFAULTS.items():
                if key == "settings" or key not in disk:
                    continue
                # se ignora cualquier campo con el tipo cambiado: un save de
                # una version futura no debe tumbar el arranque
                if default is None or isinstance(disk[key], type(default)):
                    self.data[key] = disk[key]
            self.data["settings"] = {**DEFAULT_SETTINGS, **(disk.get("settings") or {})}
        if not self.data["settings"].get("lang"):
            self.data["settings"]["lang"] = detect_lang()

    def persist(self):
        """Escritura atomica: tmp + rename, para no corromper el save si el
        proceso muere a mitad de camino (o si dos terminales lo escriben)."""
        path = save_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp.%d" % os.getpid()
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError:
            pass  # sin disco escribible el juego sigue siendo jugable

    # --- accesos comodos ---------------------------------------------------

    @property
    def settings(self):
        return self.data["settings"]

    @property
    def solutions(self):
        return self.data["solutions"]

    @property
    def levels(self):
        return self.data["levels"]

    @property
    def slots(self):
        return self.data["slots"]

    @property
    def custom(self):
        return self.data["custom"]

    def level_best(self, index):
        entry = self.levels.get(str(index))
        return entry.get("best") if entry else None

    def clear_progress(self):
        fresh = json.loads(json.dumps(DEFAULTS))
        fresh["settings"] = dict(self.data["settings"])
        self.data = fresh
        self.persist()


# --- codigos de intercambio (compatibles con la version web) ----------------


def encode_challenge(ch):
    """Serializa un desafio como "M5.<base64>", igual que encodeChallenge()."""
    cells = {tuple(c) for c in ch["cells"]}
    rows, cols = ch["rows"], ch["cols"]
    bits = "".join(
        "1" if (r, c) in cells else "0"
        for r in range(rows)
        for c in range(cols)
    )
    payload_bytes = bytes(
        int(bits[i:i + 8].ljust(8, "0"), 2) for i in range(0, len(bits), 8)
    )
    payload = json.dumps(
        {
            "n": ch["name"],
            "r": rows,
            "c": cols,
            "b": base64.b64encode(payload_bytes).decode("ascii"),
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "M5." + base64.b64encode(payload.encode("utf-8")).decode("ascii")


def decode_challenge(code):
    """Inverso de encode_challenge(). Devuelve el desafio o None si no sirve."""
    try:
        code = code.strip()
        if not code.startswith("M5."):
            return None
        raw = base64.b64decode(code[3:] + "=" * (-len(code[3:]) % 4))
        p = json.loads(raw.decode("utf-8"))
        rows, cols = int(p["r"]), int(p["c"])
        if not (1 <= rows <= 6 and 1 <= cols <= 10):
            return None
        bits = "".join(
            format(b, "08b")
            for b in base64.b64decode(p["b"] + "=" * (-len(p["b"]) % 4))
        )
        cells = [
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if r * cols + c < len(bits) and bits[r * cols + c] == "1"
        ]
        if not cells or len(cells) % 5 or len(cells) > 60:
            return None
        name = str(p.get("n") or t("imported_name"))[:24]
        return {
            "name": name,
            "cells": [list(c) for c in cells],
            "rows": rows,
            "cols": cols,
            "best": None,
            "created_at": int(time.time() * 1000),
        }
    except Exception:
        return None
