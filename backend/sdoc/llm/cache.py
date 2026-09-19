"""Content-addressed cache for model responses.

A model call is keyed by everything that could change its answer — model,
prompt, schema, images — so the same input always returns the same output
without a second call.

This is not only a cost measure. It makes a demo reproducible: the run a judge
watches produces exactly the answers we tested, at local-disk speed, with no
dependency on a third-party API being up at that moment. It also makes the
adversarial harness affordable, since re-running it after a code change only
pays for the inputs that actually changed.

Entries are plain JSON on disk under `.cache/llm/`, which is git-ignored. The
cache never stores the API key, and a corrupt or unreadable entry is treated as
a miss rather than an error.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional

CACHE_VERSION = "v1"


def cache_key(*, model: str, purpose: str, payload: Any) -> str:
    """A stable hash of everything that determines the answer.

    `sort_keys` matters: dictionaries that differ only in insertion order must
    hash the same, or the cache silently stops working.
    """
    blob = json.dumps(
        {"v": CACHE_VERSION, "model": model, "purpose": purpose, "payload": payload},
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, root: str | os.PathLike = ".cache/llm", enabled: bool = True) -> None:
        self.root = Path(root)
        self.enabled = enabled
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        # Shard by the first two characters: a flat directory of thousands of
        # files is slow to list on Windows.
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None
        path = self._path(key)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None                      # missing or corrupt: just re-ask
        self.hits += 1
        return data

    def put(self, key: str, value: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write then rename, so an interrupted run cannot leave a truncated
            # entry that would later be read back as a valid answer.
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            pass                             # a cache that cannot write is not a failure

    def record_miss(self) -> None:
        self.misses += 1

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
            "enabled": self.enabled,
        }
