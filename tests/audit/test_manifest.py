import hashlib
import logging
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from srag.audit import manifest
from srag.audit.manifest import file_sha256, git_commit


def test_file_sha256_matches_the_standard_digest(tmp_path: Path):
    file = tmp_path / "data.bin"
    file.write_bytes(b"abc")

    assert file_sha256(file) == hashlib.sha256(b"abc").hexdigest()


def test_file_sha256_reads_files_larger_than_one_chunk(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(manifest, "HASH_CHUNK_BYTES", 4)
    file = tmp_path / "data.bin"
    file.write_bytes(b"0123456789")

    assert file_sha256(file) == hashlib.sha256(b"0123456789").hexdigest()


def test_git_commit_is_none_and_logged_outside_a_repository(tmp_path: Path, caplog):
    with caplog.at_level(logging.WARNING):
        assert git_commit(tmp_path) is None

    assert "Could not read the git commit" in caplog.text


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_git_commit_returns_the_head_hash(tmp_path: Path):
    git = ["git", "-c", "user.name=test", "-c", "user.email=test@example.com"]
    subprocess.run([*git, "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        [*git, "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    assert re.fullmatch(r"[0-9a-f]{40}", git_commit(tmp_path))
