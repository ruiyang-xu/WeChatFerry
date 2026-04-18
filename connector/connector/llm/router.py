from __future__ import annotations

from dataclasses import dataclass

from .base import LlmAdapter
from .external import ExternalAdapter, ExternalLlmDeniedError
from .ollama import OllamaAdapter


@dataclass
class RouterPolicy:
    prefer_external: bool = False


class LlmRouter:
    def __init__(self, local: OllamaAdapter, external: ExternalAdapter | None) -> None:
        self.local = local
        self.external = external

    def choose(self, policy: RouterPolicy | None = None) -> LlmAdapter:
        policy = policy or RouterPolicy()
        if policy.prefer_external and self.external is not None:
            return self.external
        return self.local

    @classmethod
    def from_config(cls, cfg) -> "LlmRouter":
        local = OllamaAdapter(
            endpoint=cfg.local_llm.endpoint,
            model=cfg.local_llm.model,
            timeout_s=cfg.local_llm.timeout_s,
        )
        ext: ExternalAdapter | None = None
        if cfg.external_llm.enabled:
            try:
                ext = ExternalAdapter(
                    endpoint=cfg.external_llm.endpoint,
                    model=cfg.external_llm.model,
                    api_key_env=cfg.external_llm.api_key_env,
                    allow_domains=cfg.external_llm.allow_domains,
                    require_redaction=cfg.external_llm.require_redaction,
                )
            except ExternalLlmDeniedError:
                raise
        return cls(local=local, external=ext)
