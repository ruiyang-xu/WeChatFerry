from connector.schemas import (
    ActionItem,
    ContactHint,
    Deal,
    ExtractionResult,
    MsgKind,
    NormalizedMsg,
    Source,
    Summary,
)
from connector.storage.db import WriteHandle, connect
from connector.storage.resolver import Resolver


def _nm(i: int, thread: str = "r1", sender: str = "u1") -> NormalizedMsg:
    return NormalizedMsg(
        source=Source.WECHAT,
        source_msg_id=f"m{i}",
        thread_key=thread,
        ts=1700000000 + i,
        sender_user_id=sender,
        sender_display=sender,
        kind=MsgKind.TEXT,
        text=f"msg {i}",
    )


def test_contact_dedupe_and_merge(tmp_db):
    wh = WriteHandle(connect(tmp_db))
    r = Resolver(wh)
    r.persist_messages([_nm(1)])
    r.apply(
        ExtractionResult(contacts=[ContactHint(source=Source.WECHAT, source_user_id="u1", display_name="Alice")]),
        source=Source.WECHAT,
        window_key="wk1",
        message_id_map={"m1": 1},
    )
    r.apply(
        ExtractionResult(
            contacts=[
                ContactHint(source=Source.WECHAT, source_user_id="u1", display_name="Alice", company="Acme"),
            ]
        ),
        source=Source.WECHAT,
        window_key="wk2",
        message_id_map={},
    )
    row = wh.execute("SELECT display_name, company FROM contact WHERE source_user_id='u1'").fetchone()
    assert row["display_name"] == "Alice"
    assert row["company"] == "Acme"


def test_deal_stage_monotonicity_and_update(tmp_db):
    wh = WriteHandle(connect(tmp_db))
    r = Resolver(wh)
    r.persist_messages([_nm(1), _nm(2)])
    r.apply(
        ExtractionResult(
            deals=[Deal(title="Annual Plan", counterparty_source=Source.WECHAT, counterparty_user_id="u1",
                        stage="qualified", amount=10000, currency="USD", confidence=0.8,
                        evidence_message_ids=["m1"])],
        ),
        source=Source.WECHAT,
        window_key="wk1",
        message_id_map={"m1": 1, "m2": 2},
    )
    # New info: stage advances, amount updates because higher confidence
    r.apply(
        ExtractionResult(
            deals=[Deal(title="Annual Plan", counterparty_source=Source.WECHAT, counterparty_user_id="u1",
                        stage="proposal", amount=12000, currency="USD", confidence=0.9,
                        evidence_message_ids=["m2"])],
        ),
        source=Source.WECHAT,
        window_key="wk2",
        message_id_map={"m2": 2},
    )
    rows = wh.execute("SELECT stage, amount FROM deal").fetchall()
    assert len(rows) == 1
    assert rows[0]["stage"] == "proposal"
    assert rows[0]["amount"] == 12000

    # Regression attempt with low confidence — should stick to proposal
    r.apply(
        ExtractionResult(
            deals=[Deal(title="Annual Plan", counterparty_source=Source.WECHAT, counterparty_user_id="u1",
                        stage="lead", confidence=0.3)],
        ),
        source=Source.WECHAT,
        window_key="wk3",
        message_id_map={},
    )
    rows = wh.execute("SELECT stage FROM deal").fetchall()
    assert rows[0]["stage"] == "proposal"


def test_actions_and_summary_persist(tmp_db):
    wh = WriteHandle(connect(tmp_db))
    r = Resolver(wh)
    r.persist_messages([_nm(1)])
    r.apply(
        ExtractionResult(
            actions=[ActionItem(description="send proposal", source_message_id="m1", confidence=0.8)],
            summary=Summary(source=Source.WECHAT, thread_key="r1", window_start=1, window_end=2, bullet_points=["a"]),
        ),
        source=Source.WECHAT,
        window_key="wk",
        message_id_map={"m1": 1},
    )
    assert wh.execute("SELECT COUNT(*) c FROM action_item").fetchone()["c"] == 1
    assert wh.execute("SELECT COUNT(*) c FROM summary").fetchone()["c"] == 1
    assert wh.execute("SELECT COUNT(*) c FROM entity_link").fetchone()["c"] >= 1
