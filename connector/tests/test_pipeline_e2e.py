from connector.exporters.base import NoopExporter
from connector.llm.ollama import OllamaAdapter
from connector.llm.router import LlmRouter
from connector.pipeline import Pipeline
from connector.redact import PiiRedactor
from connector.schemas import MsgKind, NormalizedMsg, Source
from connector.storage.db import WriteHandle, connect
from connector.storage.resolver import Resolver
from connector.windowing import ConversationWindow


def _win() -> ConversationWindow:
    win = ConversationWindow(source=Source.WECHAT, thread_key="room_1")
    win.append(NormalizedMsg(
        source=Source.WECHAT, source_msg_id="msg_1",
        thread_key="room_1", ts=1712000000, sender_user_id="alice",
        sender_display="alice", kind=MsgKind.TEXT,
        text="We want the annual plan at 20000 USD, send proposal by 2026-05-01. ping bob@example.com",
    ))
    win.append(NormalizedMsg(
        source=Source.WECHAT, source_msg_id="msg_2",
        thread_key="room_1", ts=1712000100, sender_user_id="bob",
        sender_display="bob", kind=MsgKind.TEXT,
        text="Ok I'll send the proposal by Friday.",
    ))
    return win


def test_pipeline_end_to_end(tmp_db, ollama_stub):
    # Program the stub to return a valid ExtractionResult JSON.
    ollama_stub["handler"].canned = {
        "deals": [
            {
                "title": "Annual Plan",
                "counterparty_user_id": "alice",
                "stage": "proposal",
                "amount": 20000,
                "currency": "USD",
                "expected_close_date": "2026-05-01",
                "evidence_message_ids": ["msg_0", "msg_1"],
                "confidence": 0.85,
            }
        ],
        "contacts": [
            {"source_user_id": "alice", "display_name": "alice", "role": "buyer"},
            {"source_user_id": "bob", "display_name": "bob", "role": "seller"},
        ],
        "actions": [
            {
                "owner_user_id": "bob",
                "description": "Send proposal",
                "due_date": "2026-05-01",
                "source_message_id": "msg_1",
                "confidence": 0.9,
            }
        ],
        "summary": {
            "source": "wechat",
            "thread_key": "room_1",
            "window_start": 1712000000,
            "window_end": 1712000100,
            "bullet_points": ["alice wants annual plan", "bob to send proposal"],
            "decisions": [],
            "open_questions": [],
        },
    }
    wh = WriteHandle(connect(tmp_db))
    router = LlmRouter(local=OllamaAdapter(endpoint=ollama_stub["endpoint"], model="stub"), external=None)
    pipeline = Pipeline(
        wh=wh, router=router, resolver=Resolver(wh),
        redactor=PiiRedactor(), exporter=NoopExporter(),
    )
    result = pipeline.process_window(_win())
    assert result is not None
    assert wh.execute("SELECT COUNT(*) c FROM deal").fetchone()["c"] == 1
    assert wh.execute("SELECT COUNT(*) c FROM action_item").fetchone()["c"] == 1
    assert wh.execute("SELECT COUNT(*) c FROM contact").fetchone()["c"] == 2
    assert wh.execute("SELECT COUNT(*) c FROM summary").fetchone()["c"] == 1
    egress = wh.execute("SELECT adapter, host, ok FROM egress_log").fetchall()
    assert len(egress) == 1
    assert egress[0]["adapter"] == "ollama"
    assert egress[0]["ok"] == 1
