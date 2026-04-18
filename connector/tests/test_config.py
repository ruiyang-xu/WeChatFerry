import pytest

from connector.config import ConfigError, load


def _write(tmp_path, body: str):
    p = tmp_path / "c.yaml"
    p.write_text(body, encoding="utf-8")
    return str(p)


def test_defaults_load(tmp_path):
    cfg = load(_write(tmp_path, "{}"))
    assert cfg.external_llm.enabled is False
    assert cfg.external_llm.allow_domains == []


def test_external_enabled_requires_allowlist(tmp_path):
    with pytest.raises(ConfigError):
        load(_write(tmp_path, """
external_llm:
  enabled: true
  endpoint: https://api.example.com/v1
  allow_domains: []
"""))


def test_external_enabled_requires_redaction(tmp_path):
    with pytest.raises(ConfigError):
        load(_write(tmp_path, """
external_llm:
  enabled: true
  endpoint: https://api.example.com/v1
  allow_domains: [api.example.com]
  require_redaction: false
"""))


def test_external_enabled_ok(tmp_path):
    cfg = load(_write(tmp_path, """
external_llm:
  enabled: true
  endpoint: https://api.example.com/v1
  allow_domains: [api.example.com]
  require_redaction: true
"""))
    assert cfg.external_llm.enabled is True
