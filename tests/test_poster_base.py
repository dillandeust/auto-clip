from pathlib import Path
from autoclip.poster import base

def test_postresult_fields():
    r = base.PostResult(ok=True, url="u", error=None, screenshot="s.png")
    assert r.ok and r.url == "u" and r.screenshot == "s.png"

def test_login_required_is_exception():
    assert issubclass(base.LoginRequired, Exception)

def test_session_dir_is_per_platform_profile(tmp_path):
    d = base.session_dir("tiktok", "default", profiles_root=str(tmp_path))
    assert d.exists()
    assert d == Path(tmp_path) / "tiktok" / "default"
    d2 = base.session_dir("tiktok", "alt", profiles_root=str(tmp_path))
    assert d2 != d
