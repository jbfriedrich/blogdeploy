import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blogdeploy.config import parse_kv, load_blogs, load_smtp, load_config  # noqa: E402

CONF = """\
# blog registry (no secrets)
BLOGS=jre,oos
KEEP_RELEASES=5

BLOG_JRE_REPO_URL=https://github.com/jbfriedrich/jason.re.git
BLOG_JRE_BRANCH=master
BLOG_JRE_DOMAIN=jason.re
BLOG_JRE_SERVE_ROOT=/srv/jason.re

BLOG_OOS_REPO_URL=https://github.com/jbfriedrich/outofscope.blog.git
BLOG_OOS_BRANCH=main
BLOG_OOS_DOMAIN=outofscope.blog
BLOG_OOS_SERVE_ROOT=/srv/outofscope.blog
"""

ENV = {
    "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
    "SMTP_USER": "u", "SMTP_PASSWORD": "p",
    "SMTP_FROM": "deploy@jason.re", "SMTP_TO": "me@jason.re",
    "NOTIFY_ON_SUCCESS": "false",
}


def test_parse_kv_ignores_comments_and_blanks():
    kv = parse_kv("A=1\n\n# c\nB = two \n")
    assert kv == {"A": "1", "B": "two"}


def test_load_blogs_builds_registry():
    blogs = load_blogs(parse_kv(CONF))
    assert set(blogs) == {"jre", "oos"}
    jre = blogs["jre"]
    assert jre.branch == "master"
    assert jre.repo_url.endswith("jason.re.git")
    assert jre.base_url == "https://jason.re/"
    assert str(jre.releases_dir) == "/srv/jason.re/releases"
    assert str(jre.current_link) == "/srv/jason.re/current"


def test_load_smtp_reads_env():
    smtp = load_smtp(ENV)
    assert smtp.port == 465
    assert smtp.recipient == "me@jason.re"
    assert smtp.notify_on_success is False


def test_load_config_combines(tmp_path):
    p = tmp_path / "blogdeploy.conf"
    p.write_text(CONF)
    cfg = load_config(p, ENV)
    assert cfg.keep_releases == 5
    assert set(cfg.blogs) == {"jre", "oos"}
    assert cfg.smtp.host == "smtp.example.com"
