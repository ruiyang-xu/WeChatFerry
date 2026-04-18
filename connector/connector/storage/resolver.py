from __future__ import annotations

import time
from typing import Iterable

from . import dao
from .db import WriteHandle
from ..schemas import ExtractionResult, NormalizedMsg, Source


class Resolver:
    def __init__(self, wh: WriteHandle) -> None:
        self.wh = wh

    def persist_messages(self, messages: Iterable[NormalizedMsg]) -> dict[str, int]:
        """Return a map of source_msg_id -> row id for later linking."""
        out: dict[str, int] = {}
        for m in messages:
            row_id = dao.insert_message_raw(self.wh, m)
            if row_id:
                out[m.source_msg_id] = row_id
        return out

    def apply(
        self,
        result: ExtractionResult,
        *,
        source: Source,
        window_key: str,
        message_id_map: dict[str, int],
    ) -> None:
        now = int(time.time())
        for c in result.contacts:
            if c.source is None:
                c.source = source
            dao.upsert_contact(self.wh, c, now)
        for d in result.deals:
            if d.counterparty_source is None:
                d.counterparty_source = source
            deal_id = dao.upsert_deal(self.wh, d, window_key, now)
            ev_rows = [message_id_map[mid] for mid in d.evidence_message_ids if mid in message_id_map]
            dao.link_messages(self.wh, "deal", deal_id, ev_rows)
        for a in result.actions:
            if a.owner_source is None:
                a.owner_source = source
            act_id = dao.insert_action(self.wh, a, now)
            mid = message_id_map.get(a.source_message_id)
            if mid:
                dao.link_messages(self.wh, "action_item", act_id, [mid])
        if result.summary is not None:
            sum_id = dao.insert_summary(self.wh, result.summary, now)
            dao.link_messages(self.wh, "summary", sum_id, message_id_map.values())
