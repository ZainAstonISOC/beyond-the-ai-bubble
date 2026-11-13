"""Raw-data fetching with an audit manifest.

Every download is written unmodified to data/raw/<source>/ and recorded in
data/raw/manifest.json with its URL, retrieval timestamp (UTC) and SHA-256.
Raw files are never edited after download.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "manifest.json"
UA = "HowdenResearch research@howdenresearch.uk"


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def _save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=1, sort_keys=True))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(source: str, name: str, url: str, retries: int = 3, ua: str = UA) -> Path:
    """Download url to data/raw/<source>/<name> and record it in the manifest."""
    out = RAW / source / name
    out.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            out.write_bytes(data)
            break
        except Exception as e:  # network errors are retried, then raised
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"fetch failed for {url}: {last}")
    record_local(source, name, url)
    return out


def record_local(source: str, name: str, origin: str) -> None:
    """Record a file already placed in data/raw (e.g. a manual download)."""
    path = RAW / source / name
    m = _load_manifest()
    m[f"{source}/{name}"] = {
        "origin": origin,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    _save_manifest(m)
