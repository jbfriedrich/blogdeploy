"""Entrypoint: `python -m blogdeploy <blogkey>` — build one blog, email on failure."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .build import BuildError, build_blog
from .config import Config, load_config
from .notify import format_email, send_email

DEFAULT_CONF = Path(os.environ.get("BLOGDEPLOY_CONF", "/etc/blogdeploy/blogdeploy.conf"))


def main(argv: list[str], *, config: Config | None = None,
         builder=build_blog, mailer=send_email) -> int:
    if len(argv) != 1:
        print("usage: python -m blogdeploy <blogkey>", file=sys.stderr)
        return 2
    cfg = config or load_config(DEFAULT_CONF, os.environ)
    key = argv[0]
    blog = cfg.blogs.get(key)
    if blog is None:
        print(f"unknown blog: {key} (known: {', '.join(cfg.blogs)})", file=sys.stderr)
        return 2
    try:
        release = builder(blog, cfg.keep_releases)
        print(f"published {key} -> {release}")
        if cfg.smtp.notify_on_success:
            mailer(format_email(key, "success", f"published {release}", cfg.smtp, success=True), cfg.smtp)
        return 0
    except BuildError as e:
        mailer(format_email(key, e.step, str(e), cfg.smtp), cfg.smtp)
        print(f"deploy failed at {e.step}: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — last-ditch: still notify
        mailer(format_email(key, "unknown", repr(e), cfg.smtp), cfg.smtp)
        print(f"deploy failed: {e!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
