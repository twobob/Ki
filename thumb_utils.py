from pathlib import Path
import hashlib


def folder_hash(path: Path) -> str:
    """Return a short, deterministic hash for the given directory path."""
    return hashlib.blake2s(str(path.resolve()).encode("utf-8"), digest_size=4).hexdigest()
