from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(ValueError):
    pass


@dataclass
class LocalLlmCfg:
    endpoint: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b-instruct"
    timeout_s: int = 60


@dataclass
class ExternalLlmCfg:
    enabled: bool = False
    provider: str = "openai_compat"
    endpoint: str = ""
    model: str = ""
    api_key_env: str = "CONNECTOR_EXTERNAL_API_KEY"
    allow_domains: list[str] = field(default_factory=list)
    require_redaction: bool = True


@dataclass
class StorageCfg:
    db_path: str = "./connector.db"
    raw_msg_ttl_days: int = 30


@dataclass
class WindowingCfg:
    max_messages: int = 30
    idle_seconds: int = 90
    max_wall_minutes: int = 15


@dataclass
class WeChatSourceCfg:
    enabled: bool = False
    wcferry_host: str = "127.0.0.1"
    wcferry_port: int = 10086


@dataclass
class FeishuSourceCfg:
    enabled: bool = False
    bind: str = "127.0.0.1"
    port: int = 8701
    verification_token_env: str = "FEISHU_VERIFICATION_TOKEN"
    encrypt_key_env: str = "FEISHU_ENCRYPT_KEY"


@dataclass
class SlackSourceCfg:
    enabled: bool = False
    bind: str = "127.0.0.1"
    port: int = 8702
    signing_secret_env: str = "SLACK_SIGNING_SECRET"


@dataclass
class SourcesCfg:
    wechat: WeChatSourceCfg = field(default_factory=WeChatSourceCfg)
    feishu: FeishuSourceCfg = field(default_factory=FeishuSourceCfg)
    slack: SlackSourceCfg = field(default_factory=SlackSourceCfg)


@dataclass
class ExporterCfg:
    kind: str = "none"


@dataclass
class ConnectorConfig:
    local_llm: LocalLlmCfg = field(default_factory=LocalLlmCfg)
    external_llm: ExternalLlmCfg = field(default_factory=ExternalLlmCfg)
    storage: StorageCfg = field(default_factory=StorageCfg)
    windowing: WindowingCfg = field(default_factory=WindowingCfg)
    sources: SourcesCfg = field(default_factory=SourcesCfg)
    exporter: ExporterCfg = field(default_factory=ExporterCfg)


def _build_source(d: dict) -> SourcesCfg:
    d = d or {}
    return SourcesCfg(
        wechat=WeChatSourceCfg(**(d.get("wechat") or {})),
        feishu=FeishuSourceCfg(**(d.get("feishu") or {})),
        slack=SlackSourceCfg(**(d.get("slack") or {})),
    )


def load(path: str | Path) -> ConnectorConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg = ConnectorConfig(
        local_llm=LocalLlmCfg(**(raw.get("local_llm") or {})),
        external_llm=ExternalLlmCfg(**(raw.get("external_llm") or {})),
        storage=StorageCfg(**(raw.get("storage") or {})),
        windowing=WindowingCfg(**(raw.get("windowing") or {})),
        sources=_build_source(raw.get("sources") or {}),
        exporter=ExporterCfg(**(raw.get("exporter") or {})),
    )
    _validate(cfg)
    return cfg


def _validate(cfg: ConnectorConfig) -> None:
    # Fail-closed external LLM gating.
    ext = cfg.external_llm
    if ext.enabled:
        if not ext.require_redaction:
            raise ConfigError("external_llm.require_redaction must remain true")
        if not ext.allow_domains:
            raise ConfigError("external_llm.allow_domains must be non-empty when enabled")
        if not ext.endpoint:
            raise ConfigError("external_llm.endpoint must be set when enabled")
