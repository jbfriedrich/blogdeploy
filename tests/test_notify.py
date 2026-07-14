import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blogdeploy.config import SMTPConfig  # noqa: E402
from blogdeploy.notify import format_email  # noqa: E402

SMTP = SMTPConfig("smtp.example.com", 465, "u", "p", "deploy@jason.re", "me@jason.re", False)


def test_failure_email_has_blog_step_and_detail():
    msg = format_email("jre", "build", "hugo exited 1\ntemplate error", SMTP)
    assert msg["From"] == "deploy@jason.re"
    assert msg["To"] == "me@jason.re"
    assert "jre" in msg["Subject"] and "fail" in msg["Subject"].lower()
    body = msg.get_content()
    assert "build" in body and "template error" in body


def test_success_email_subject_says_succeeded():
    msg = format_email("oos", "success", "published .../20260708T100000Z", SMTP, success=True)
    assert "succeeded" in msg["Subject"].lower()
    assert "fail" not in msg["Subject"].lower()
