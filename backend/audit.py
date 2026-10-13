"""Append-only audit trail at output/audit_trail.json.

The file is one JSON array. New entries are spliced in before the closing
bracket, so earlier entries are never rewritten or wiped, across every run.
"""

import json
import threading
from pathlib import Path
from typing import Any

from .config import AUDIT_TRAIL

_lock = threading.Lock()


def read_audit(path: Path = AUDIT_TRAIL) -> list[dict[str, Any]]:
    """Read every entry (under the same lock as the writer, so a read never sees half a write)."""
    with _lock:
        if not path.exists() or path.stat().st_size == 0:
            return []
        return json.loads(path.read_text(encoding="utf-8"))


def append_audit(entry: dict[str, Any], path: Path = AUDIT_TRAIL) -> None:
    line = json.dumps(entry, default=str, ensure_ascii=False).encode("utf-8")
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.stat().st_size == 0:
            path.write_bytes(b"[\n" + line + b"\n]\n")
            return
        with path.open("r+b") as f:
            # Walk back past trailing whitespace to the closing bracket.
            pos = f.seek(0, 2)
            while pos > 0:
                f.seek(pos - 1)
                ch = f.read(1)
                if not ch.isspace():
                    break
                pos -= 1
            if ch != b"]":
                raise ValueError(
                    f"{path} does not end with ']'. Refusing to touch it so no entries are lost."
                )
            f.seek(pos - 1)
            f.write(b",\n" + line + b"\n]\n")
            f.truncate()
