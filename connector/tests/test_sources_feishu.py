from connector.sources.feishu.normalize import event_to_normalized
from connector.schemas import MsgKind, Source


def test_feishu_text_event():
    ev = {
        "schema": "2.0",
        "header": {"token": "tok"},
        "event": {
            "message": {
                "message_id": "om_1",
                "create_time": "1712000000000",
                "chat_id": "oc_1",
                "chat_type": "group",
                "message_type": "text",
                "content": "{\"text\": \"hello\"}",
            },
            "sender": {"sender_id": {"open_id": "ou_alice"}},
        },
    }
    nm = event_to_normalized(ev)
    assert nm is not None
    assert nm.source == Source.FEISHU
    assert nm.source_msg_id == "om_1"
    assert nm.thread_key == "oc_1"
    assert nm.sender_user_id == "ou_alice"
    assert nm.text == "hello"
    assert nm.kind == MsgKind.TEXT
    assert nm.ts == 1712000000
