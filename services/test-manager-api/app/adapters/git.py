"""Git operations for generated test branches and commits."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.config import settings
from app.core.errors import BadRequestError, DependencyUnavailableError

logger = logging.getLogger("app.git")


def _run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    if check and result.returncode != 0:
        raise BadRequestError(f"git command failed: {' '.join(cmd[:4])}... {result.stderr[-500:]}")
    return result


class GitService:
    """Creates a branch, commits generated tests and pushes (optionally)."""

    def __init__(self, root: str | None = None):
        self._root = Path(root or settings.storage_local_root) / "generated_tests"

    @property
    def root(self) -> Path:
        return self._root

    def ensure_repo(self) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        if not (self._root / ".git").exists():
            _run(["git", "init", "-b", "main"], cwd=self._root)
            _run(["git", "config", "user.email", "uat-platform@local"],
                 cwd=self._root)
            _run(["git", "config", "user.name", "UAT Test Platform"], cwd=self._root)
        return self._root

    def create_branch(self, branch: str) -> None:
        repo = self.ensure_repo()
        _run(["git", "checkout", "-B", branch], cwd=repo)

    def write_file(self, rel_path: str, content: str) -> Path:
        repo = self.ensure_repo()
        dest = repo / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        return dest

    def commit(self, message: str) -> str:
        repo = self.ensure_repo()
        _run(["git", "add", "-A"], cwd=repo)
        result = _run(["git", "commit", "-m", message], cwd=repo, check=False)
        if result.returncode != 0:
            logger.info("commit returned non-zero (likely nothing to commit)")
        return _run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    def push(self, branch: str) -> bool:
        remote_url = settings.azure_git_remote_url
        if not remote_url:
            return False
        repo = self.ensure_repo()
        _run(["git", "remote", "remove", "origin"], cwd=repo, check=False)
        _run(["git", "remote", "add", "origin", remote_url], cwd=repo)
        result = _run(
            ["git", "push", "-u", "origin", branch], cwd=repo, check=False
        )
        if result.returncode != 0:
            logger.warning("push failed: %s", result.stderr[-500:])
            raise DependencyUnavailableError(f"git push failed: {result.stderr[-300:]}")
        return True
