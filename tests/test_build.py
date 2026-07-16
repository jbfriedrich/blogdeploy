import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blogdeploy.build import atomic_symlink, prune_releases, publish  # noqa: E402
from blogdeploy.build import BuildError, build_blog  # noqa: E402
from blogdeploy.config import BlogConfig  # noqa: E402


def _blog(root: Path) -> BlogConfig:
    return BlogConfig("jre", "url", "master", "jason.re", str(root))


def _built(tmp: Path, marker: str) -> Path:
    d = tmp / "build" / "public"
    d.mkdir(parents=True)
    (d / "index.html").write_text(marker)
    return d


def test_atomic_symlink_replaces_existing(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    link = tmp_path / "current"
    atomic_symlink(a, link)
    assert link.resolve() == a.resolve()
    atomic_symlink(b, link)                 # replace, must not raise
    assert link.resolve() == b.resolve()


def test_publish_swaps_current_and_serves_new(tmp_path):
    blog = _blog(tmp_path / "srv")
    rel = publish(_built(tmp_path, "v1"), blog, keep=5, now="20260708T100000Z")
    assert rel == blog.releases_dir / "20260708T100000Z"
    assert (blog.current_link / "index.html").read_text() == "v1"
    rel2 = publish(_built(tmp_path, "v2"), blog, keep=5, now="20260708T110000Z")
    assert (blog.current_link / "index.html").read_text() == "v2"
    assert rel.exists() and rel2.exists()   # both releases retained (keep=5)


def test_prune_keeps_newest_and_protects_current(tmp_path):
    releases = tmp_path / "releases"
    releases.mkdir()
    stamps = ["20260708T0%d0000Z" % i for i in range(1, 8)]  # 7 releases
    for s in stamps:
        (releases / s).mkdir()
    protect = releases / stamps[-1]
    removed = prune_releases(releases, keep=5, protect=protect)
    remaining = sorted(p.name for p in releases.iterdir())
    assert len(remaining) == 5
    assert stamps[-1] in remaining          # newest kept
    assert stamps[0] in {p.name for p in removed}  # oldest removed


class FakeRunner:
    """Records commands + env per step; simulates git clone by writing a fake built site."""
    def __init__(self, fail_step: str | None = None):
        self.calls: list[tuple[str, list[str]]] = []
        self.envs: dict[str, dict] = {}
        self.fail_step = fail_step

    def __call__(self, cmd, *, cwd=None, env=None, step=""):
        self.calls.append((step, cmd))
        self.envs[step] = env or {}
        if step == self.fail_step:
            raise BuildError(step, f"simulated {step} failure")
        if step == "build":
            # emulate hugo writing public/ into the clone dir (destination is cmd-derived)
            dest = Path(cmd[cmd.index("--destination") + 1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "index.html").write_text("built")


def test_build_blog_runs_clone_then_build_then_publishes(tmp_path):
    blog = BlogConfig("jre", "https://x/jason.re.git", "master", "jason.re", str(tmp_path / "srv"))
    runner = FakeRunner()
    rel = build_blog(blog, keep=5, runner=runner, now="20260708T120000Z",
                     workdir=str(tmp_path / "work"), cache_root=str(tmp_path / "cache"))
    steps = [s for s, _ in runner.calls]
    assert steps == ["clone", "build"]
    # clone used the right branch + flags
    clone_cmd = runner.calls[0][1]
    assert "--recurse-submodules" in clone_cmd and "--depth" in clone_cmd
    assert clone_cmd[clone_cmd.index("--branch") + 1] == "master"
    # published and served
    assert (blog.current_link / "index.html").read_text() == "built"
    assert rel.name == "20260708T120000Z"
    # temp build context cleaned up
    assert not (tmp_path / "work").exists()


def test_build_blog_cleans_up_and_raises_on_build_failure(tmp_path):
    blog = BlogConfig("jre", "https://x/jason.re.git", "master", "jason.re", str(tmp_path / "srv"))
    runner = FakeRunner(fail_step="build")
    try:
        build_blog(blog, keep=5, runner=runner, now="20260708T130000Z",
                   workdir=str(tmp_path / "work"), cache_root=str(tmp_path / "cache"))
        assert False, "expected BuildError"
    except BuildError as e:
        assert e.step == "build"
    assert not blog.current_link.exists()      # live site never touched
    assert not (tmp_path / "work").exists()    # context cleaned even on failure


def test_build_blog_wires_and_creates_persistent_cache(tmp_path):
    blog = BlogConfig("jre", "https://x/jason.re.git", "master", "jason.re", str(tmp_path / "srv"))
    cache_root = tmp_path / "cache"
    runner = FakeRunner()
    build_blog(blog, keep=5, runner=runner, now="20260716T120000Z",
               workdir=str(tmp_path / "work"), cache_root=str(cache_root))
    env = runner.envs["build"]
    assert env["HUGO_RESOURCEDIR"] == str(cache_root / "jre" / "resources")
    assert env["HUGO_CACHEDIR"] == str(cache_root / "jre" / "cache")
    # cache dirs persist — they live outside the cleaned-up workdir
    assert (cache_root / "jre" / "resources").is_dir()
    assert (cache_root / "jre" / "cache").is_dir()
    assert not (tmp_path / "work").exists()


def test_build_blog_reuses_existing_cache(tmp_path):
    blog = BlogConfig("jre", "https://x/jason.re.git", "master", "jason.re", str(tmp_path / "srv"))
    cache_root = tmp_path / "cache"
    marker = cache_root / "jre" / "resources" / "_gen" / "keep.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text("cached")
    runner = FakeRunner()
    build_blog(blog, keep=5, runner=runner, now="20260716T130000Z",
               workdir=str(tmp_path / "work"), cache_root=str(cache_root))
    assert marker.read_text() == "cached"   # existing cache reused, not clobbered
