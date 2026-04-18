import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from connector.schemas import Source
from connector.sources.slack.normalize import event_to_normalized
from connector.sources.slack.webhook import SlackSource


def test_slack_normalize_event():
    ev = {
        "type": "event_callback",
        "team_id": "T1",
        "event": {
            "type": "message",
            "ts": "1712000000.000100",
            "channel": "C1",
            "user": "U1",
            "text": "hello",
        },
    }
    nm = event_to_normalized(ev)
    assert nm is not None
    assert nm.source == Source.SLACK
    assert nm.sender_user_id == "U1"
    assert nm.thread_key == "C1"


def _sig(secret: bytes, ts: str, body: bytes) -> str:
    base = b"v0:" + ts.encode() + b":" + body
    mac = hmac.new(secret, base, hashlib.sha256).hexdigest()
    return f"v0={mac}"


def test_slack_webhook_signature_ok(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret123")
    import queue
    q = queue.Queue()
    src = SlackSource(inbound=q)
    client = TestClient(src.app)
    body = json.dumps({"type": "url_verification", "challenge": "xyz"}).encode()
    ts = str(int(time.time()))
    sig = _sig(b"secret123", ts, body)
    resp = client.post(
        "/webhook/slack",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "xyz"


def test_slack_webhook_signature_rejected(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret123")
    import queue
    q = queue.Queue()
    src = SlackSource(inbound=q)
    client = TestClient(src.app)
    body = json.dumps({"type": "event_callback"}).encode()
    ts = str(int(time.time()))
    resp = client.post(
        "/webhook/slack",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": "v0=bad",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401
