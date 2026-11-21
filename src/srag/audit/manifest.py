"""Run manifest: the configuration, provenance and totals of one report run."""

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from srag.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"
HASH_CHUNK_BYTES = 1024 * 1024
GIT_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class ManifestInfo:
    """What the caller knows about the run; the logger adds the id, times and totals."""

    uf: str | None
    model: str
    prompt_versions: dict[str, str] = field(default_factory=dict)
    data_file: Path | None = None
    data_max_date: date | None = None


def file_sha256(path: Path) -> str:
    """SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(project_root: Path = PROJECT_ROOT) -> str | None:
    """Current commit hash, or None when git is unavailable (logged, not hidden)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("Could not read the git commit: %s", type(error).__name__)
        return None
    return result.stdout.strip() or None


def write_manifest_file(path: Path, content: dict) -> Path:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, default=str), "utf-8")
    return path
