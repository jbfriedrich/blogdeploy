"""Build & publish: clone -> hugo -> atomic release swap. Stdlib only."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .config import BlogConfig


def atomic_symlink(target: Path, link: Path) -> None:
    """Point `link` at `target` atomically, replacing any existing `link`."""
    tmp = link.with_name(link.name + ".tmp")
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    tmp.symlink_to(target)
    os.replace(tmp, link)  # atomic rename over an existing symlink


def prune_releases(releases_dir: Path, keep: int, *, protect: Path | None = None) -> list[Path]:
    """Delete all but the newest `keep` release dirs (by name). Never delete `protect`."""
    dirs = sorted((p for p in releases_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    removed: list[Path] = []
    for p in dirs[:-keep] if keep > 0 else []:
        if protect is not None and p.resolve() == protect.resolve():
            continue
        shutil.rmtree(p)
        removed.append(p)
    return removed


def publish(built_dir: Path, blog: BlogConfig, keep: int, *, now: str) -> Path:
    """Move `built_dir` into releases/<now>, swap `current`, prune. Return the release path."""
    releases = blog.releases_dir
    releases.mkdir(parents=True, exist_ok=True)
    release = releases / now
    if release.exists():
        raise FileExistsError(f"release already exists: {release}")
    shutil.move(str(built_dir), str(release))     # handles cross-filesystem moves
    atomic_symlink(release, blog.current_link)
    prune_releases(releases, keep, protect=release)
    return release


class BuildError(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step


def run(cmd: list[str], *, cwd: str | None = None, env: dict | None = None, step: str = "") -> None:
    proc = subprocess.run(
        cmd, cwd=cwd, env={**os.environ, **(env or {})},
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout)[-2000:]
        raise BuildError(step, f"{' '.join(cmd)} exited {proc.returncode}\n{tail}")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_blog(blog: BlogConfig, keep: int, *, runner=run, now: str | None = None,
               workdir: str | None = None) -> Path:
    now = now or utc_stamp()
    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix=f"blogdeploy-{blog.key}-"))
    tmp.mkdir(parents=True, exist_ok=True)
    clone = tmp / "src"
    public = tmp / "public"
    try:
        runner(
            ["git", "clone", "--recurse-submodules", "--depth", "1",
             "--branch", blog.branch, blog.repo_url, str(clone)],
            step="clone",
        )
        runner(
            ["hugo", "--gc", "--minify", "--source", str(clone),
             "--destination", str(public), "--baseURL", blog.base_url],
            env={"HUGO_ENVIRONMENT": "production", "TZ": "Europe/Berlin"},
            step="build",
        )
        return publish(public, blog, keep, now=now)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
