import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blogdeploy.build import BuildError  # noqa: E402
from blogdeploy.config import BlogConfig, Config, SMTPConfig  # noqa: E402
from blogdeploy.__main__ import main  # noqa: E402

SMTP = SMTPConfig("h", 465, "u", "p", "f@x", "t@x", False)


def _cfg(tmp):
    blog = BlogConfig("jre", "url", "master", "jason.re", str(tmp))
    return Config(blogs={"jre": blog}, smtp=SMTP, keep_releases=5)


def test_main_unknown_blog_is_usage_error(tmp_path, capsys):
    rc = main(["nope"], config=_cfg(tmp_path))
    assert rc == 2


def test_main_success_returns_zero(tmp_path):
    calls = {}
    def builder(blog, keep, **kw): calls["built"] = blog.key; return Path("/x")
    def mailer(msg, smtp): calls["mailed"] = True
    rc = main(["jre"], config=_cfg(tmp_path), builder=builder, mailer=mailer)
    assert rc == 0 and calls == {"built": "jre"}    # no mail on success


def test_main_build_failure_mails_and_returns_one(tmp_path):
    sent = {}
    def builder(blog, keep, **kw): raise BuildError("build", "boom")
    def mailer(msg, smtp): sent["subject"] = msg["Subject"]
    rc = main(["jre"], config=_cfg(tmp_path), builder=builder, mailer=mailer)
    assert rc == 1
    assert "jre" in sent["subject"] and "build" in sent["subject"]
