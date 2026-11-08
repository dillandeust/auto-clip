from autoclip import config

def test_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("AUTOCLIP_DB", raising=False)
    monkeypatch.delenv("AUTOCLIP_HEADLESS", raising=False)
    monkeypatch.delenv("AUTOCLIP_MAX_ATTEMPTS", raising=False)
    cfg = config.load()
    assert cfg.db_path.endswith("autoclip.db")
    assert cfg.headless is False
    assert cfg.max_attempts == 3

def test_env_override(monkeypatch):
    monkeypatch.setenv("AUTOCLIP_HEADLESS", "true")
    monkeypatch.setenv("AUTOCLIP_MAX_ATTEMPTS", "5")
    cfg = config.load()
    assert cfg.headless is True
    assert cfg.max_attempts == 5
