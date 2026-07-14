"""Config: a non-secret KEY=VALUE blog registry + SMTP from the environment."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def parse_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


@dataclass(frozen=True)
class BlogConfig:
    key: str
    repo_url: str
    branch: str
    domain: str
    serve_root: str

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}/"

    @property
    def releases_dir(self) -> Path:
        return Path(self.serve_root) / "releases"

    @property
    def current_link(self) -> Path:
        return Path(self.serve_root) / "current"


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipient: str
    notify_on_success: bool


@dataclass(frozen=True)
class Config:
    blogs: dict[str, BlogConfig]
    smtp: SMTPConfig
    keep_releases: int


def load_blogs(conf: Mapping[str, str]) -> dict[str, BlogConfig]:
    keys = [k.strip() for k in conf.get("BLOGS", "").split(",") if k.strip()]
    blogs: dict[str, BlogConfig] = {}
    for key in keys:
        p = f"BLOG_{key.upper()}_"
        blogs[key] = BlogConfig(
            key=key,
            repo_url=conf[p + "REPO_URL"],
            branch=conf[p + "BRANCH"],
            domain=conf[p + "DOMAIN"],
            serve_root=conf[p + "SERVE_ROOT"],
        )
    return blogs


def load_smtp(env: Mapping[str, str]) -> SMTPConfig:
    return SMTPConfig(
        host=env["SMTP_HOST"],
        port=int(env.get("SMTP_PORT", "465")),
        user=env["SMTP_USER"],
        password=env["SMTP_PASSWORD"],
        sender=env["SMTP_FROM"],
        recipient=env["SMTP_TO"],
        notify_on_success=env.get("NOTIFY_ON_SUCCESS", "false").lower() == "true",
    )


def load_config(conf_path: Path, env: Mapping[str, str]) -> Config:
    conf = parse_kv(Path(conf_path).read_text(encoding="utf-8"))
    return Config(
        blogs=load_blogs(conf),
        smtp=load_smtp(env),
        keep_releases=int(conf.get("KEEP_RELEASES", "5")),
    )
