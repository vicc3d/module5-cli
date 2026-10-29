"""On-disk persistence and challenge exchange codes.

The web version saved to localStorage; here a single JSON file lives in the
user's data directory (XDG on Linux, Application Support on macOS). The
"M5.…" code format is identical to the web's, so a challenge created in the
terminal can be imported in the browser and back.
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
    "lang": None,      # None = detect from the environment on first launch
    "theme": "neon",
    "mouse": True,
}

DEFAULTS = {
    "schema": SCHEMA,
    "solutions": [],     # canonical solutions of classic mode
    "classic_best": None,
    "levels": {},        # "index" -> {"best": ms}
    "slots": {},         # "0".."4" -> snapshot
    "custom": [],        # user-created challenges
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
    """The progress file, loaded into memory and written atomically."""

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
                # any field with a changed type is ignored: a save from a
                # future version shouldn't crash startup
                if default is None or isinstance(disk[key], type(default)):
                    self.data[key] = disk[key]
            saved = disk.get("settings")
            if isinstance(saved, dict):
                self.data["settings"] = {**DEFAULT_SETTINGS, **saved}
        if not self.data["settings"].get("lang"):
            self.data["settings"]["lang"] = detect_lang()

    def persist(self):
        """Atomic write: tmp + rename, so the save doesn't get corrupted if
        the process dies mid-write (or if two terminals write it)."""
        path = save_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp.%d" % os.getpid()
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError:
            pass  # without writable disk the game is still playable

    # Convenience accessors

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


# Exchange codes (compatible with the web version)


def encode_challenge(ch):
    """Serializes a challenge as "M5.<base64>", same as encodeChallenge()."""
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
    """Inverse of encode_challenge(). Returns the challenge or None if invalid."""
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
