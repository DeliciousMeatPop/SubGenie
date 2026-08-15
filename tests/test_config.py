"""Tests for config defaults, serialization, and the ask logic."""

from subgenie import config


def test_roundtrip_serialization():
    cfg = config.Config()
    cfg.api_key = "abc"
    cfg.defaults.languages = ["en", "es"]
    cfg.defaults.action = config.ACTION_EMBED
    cfg.prompts.mode = config.MODE_SMART
    cfg.updates.check_on_run = False
    cfg.updates.last_check = 1234.5
    restored = config.Config.from_dict(cfg.to_dict())
    assert restored.api_key == "abc"
    assert restored.defaults.languages == ["en", "es"]
    assert restored.defaults.action == config.ACTION_EMBED
    assert restored.prompts.mode == config.MODE_SMART
    assert restored.updates.check_on_run is False
    assert restored.updates.last_check == 1234.5


def test_should_ask_mode_never():
    cfg = config.Config()
    cfg.prompts.mode = config.MODE_NEVER
    cfg.prompts.languages = config.ASK
    assert cfg.should_ask("languages") is False


def test_should_ask_mode_always():
    cfg = config.Config()
    cfg.prompts.mode = config.MODE_ALWAYS
    cfg.prompts.languages = config.NEVER
    assert cfg.should_ask("languages") is True


def test_should_ask_mode_smart_respects_per_decision():
    cfg = config.Config()
    cfg.prompts.mode = config.MODE_SMART
    cfg.prompts.languages = config.ASK
    cfg.prompts.action = config.NEVER
    assert cfg.should_ask("languages") is True
    assert cfg.should_ask("action") is False


def test_save_and_load_uses_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_dir", lambda: str(tmp_path))
    monkeypatch.setattr(config, "config_path", lambda: str(tmp_path / "config.json"))
    cfg = config.Config()
    cfg.api_key = "xyz"
    cfg.defaults.action = config.ACTION_EMBED
    config.save(cfg)
    loaded = config.load()
    assert loaded.api_key == "xyz"
    assert loaded.defaults.action == config.ACTION_EMBED


def test_load_missing_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_path", lambda: str(tmp_path / "none.json"))
    loaded = config.load()
    assert loaded.api_key == ""
    assert loaded.prompts.mode == config.MODE_SMART
