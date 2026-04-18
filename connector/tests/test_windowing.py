import time

from connector.schemas import MsgKind, NormalizedMsg, Source
from connector.windowing import WindowStore


def _msg(i: int, thread: str = "room1", ts: int | None = None) -> NormalizedMsg:
    return NormalizedMsg(
        source=Source.WECHAT,
        source_msg_id=f"m{i}",
        thread_key=thread,
        ts=ts if ts is not None else int(time.time()),
        sender_user_id=f"u{i%3}",
        sender_display="u",
        kind=MsgKind.TEXT,
        text=f"hello {i}",
    )


def test_flush_on_count():
    store = WindowStore(max_messages=5, idle_seconds=9999, max_wall_minutes=9999)
    for i in range(5):
        store.append(_msg(i))
    due = store.due_for_flush()
    assert len(due) == 1
    assert len(due[0].messages) == 5


def test_flush_on_idle():
    store = WindowStore(max_messages=1000, idle_seconds=30, max_wall_minutes=9999)
    past = int(time.time()) - 100
    store.append(_msg(0, ts=past))
    due = store.due_for_flush()
    assert len(due) == 1


def test_separate_threads_do_not_merge():
    store = WindowStore(max_messages=2, idle_seconds=9999, max_wall_minutes=9999)
    store.append(_msg(0, thread="a"))
    store.append(_msg(1, thread="b"))
    assert store.due_for_flush() == []
    store.append(_msg(2, thread="a"))
    store.append(_msg(3, thread="b"))
    due = store.due_for_flush()
    threads = {w.thread_key for w in due}
    assert threads == {"a", "b"}
