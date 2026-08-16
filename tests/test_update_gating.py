"""Tests for when the automatic update check is due."""

from subgenie import config
from subgenie.cli import _update_check_due


def _cfg(check_on_run=True, interval=0.0, last_check=0.0):
    cfg = config.Config()
    cfg.updates.check_on_run = check_on_run
    cfg.updates.check_interval_hours = interval
    cfg.updates.last_check = last_check
    return cfg


def test_checks_every_run_by_default():
    cfg = _cfg()  # interval 0 -> always
    now = 1_000_000.0
    # Even if we "just checked", a zero interval means check again.
    cfg.updates.last_check = now
    assert _update_check_due(cfg, now) is True


def test_disabled_never_checks():
    assert _update_check_due(_cfg(check_on_run=False), 1_000_000.0) is False


def test_interval_throttles():
    now = 1_000_000.0
    cfg = _cfg(interval=24.0, last_check=now - 3600)  # 1h ago, interval 24h
    assert _update_check_due(cfg, now) is False
    cfg.updates.last_check = now - 25 * 3600           # 25h ago
    assert _update_check_due(cfg, now) is True


def test_config_roundtrip_includes_interval():
    cfg = config.Config()
    cfg.updates.check_interval_hours = 12.0
    cfg.updates.check_on_run = True
    restored = config.Config.from_dict(cfg.to_dict())
    assert restored.updates.check_interval_hours == 12.0
    # Default is 0.0 (every run).
    assert config.Config().updates.check_interval_hours == 0.0
