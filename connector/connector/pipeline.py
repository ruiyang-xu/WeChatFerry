from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .audit import record as audit_record
from .exporters.base import Exporter, NoopExporter
from .llm.base import LlmCall
from .llm.router import LlmRouter, RouterPolicy
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .redact import PiiRedactor
from .schemas import ExtractionResult
from .storage.db import WriteHandle
from .storage.resolver import Resolver
from .windowing import ConversationWindow

LOG = logging.getLogger(__name__)


@dataclass
class Pipeline:
    wh: WriteHandle
    router: LlmRouter
    resolver: Resolver
    redactor: PiiRedactor
    exporter: Exporter = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.exporter is None:
            self.exporter = NoopExporter()

    def process_window(self, win: ConversationWindow) -> ExtractionResult | None:
        if not win.messages:
            return None
        # Assign synthetic local ids to each message for the LLM to cite.
        for idx, m in enumerate(win.messages):
            m.raw.setdefault("_cite_id", f"msg_{idx}")
        transcript_lines = []
        for m in win.messages:
            cite = m.raw.get("_cite_id", "")
            who = m.sender_display or m.sender_user_id
            transcript_lines.append(f"[{m.ts}] {who} ({cite}): {m.text}")
        transcript = "\n".join(transcript_lines)

        redaction = self.redactor.apply(transcript)
        user = build_user_prompt(
            transcript=redaction.text,
            source=win.source.value,
            thread_key=win.thread_key,
        )
        window_key = f"{win.source.value}:{win.thread_key}:{win.first_ts}-{win.last_ts}"

        adapter = self.router.choose(RouterPolicy())
        content, call = adapter.extract_json(SYSTEM_PROMPT, user, window_key)
        audit_record(self.wh, call, payload=redaction.text, window_key=window_key)
        if not call.ok or not content:
            LOG.warning("LLM call failed for window %s: %s", window_key, call.error)
            return None

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            LOG.warning("LLM returned non-JSON for window %s: %s", window_key, exc)
            return None

        rehydrated = self.redactor.rehydrate(parsed, redaction.reverse_map)
        try:
            result = ExtractionResult.model_validate(rehydrated)
        except Exception as exc:  # pydantic ValidationError
            LOG.warning("Schema validation failed for window %s: %s", window_key, exc)
            return None

        # Translate cite ids in result back to source_msg_id for linking.
        cite_to_srcid = {m.raw.get("_cite_id"): m.source_msg_id for m in win.messages}
        for d in result.deals:
            d.evidence_message_ids = [cite_to_srcid.get(cid, cid) for cid in d.evidence_message_ids]
        for a in result.actions:
            a.source_message_id = cite_to_srcid.get(a.source_message_id, a.source_message_id)

        msg_id_map = self.resolver.persist_messages(win.messages)
        self.resolver.apply(
            result,
            source=win.source,
            window_key=window_key,
            message_id_map=msg_id_map,
        )
        self.exporter.export(win.source.value, win.thread_key, result)
        return result
