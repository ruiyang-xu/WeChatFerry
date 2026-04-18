from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict


class Source(str, Enum):
    WECHAT = "wechat"
    FEISHU = "feishu"
    SLACK = "slack"


class MsgKind(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"
    OTHER = "other"


class NormalizedMsg(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: Source
    source_msg_id: str
    thread_key: str                 # roomid for groups; peer id for 1:1
    ts: int                         # unix seconds
    sender_user_id: str             # source-native id (wxid, open_id, slack user id)
    sender_display: str = ""
    kind: MsgKind = MsgKind.TEXT
    text: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


Stage = Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]

STAGE_ORDER: dict[str, int] = {
    "lead": 0,
    "qualified": 1,
    "proposal": 2,
    "negotiation": 3,
    "won": 4,
    "lost": 4,
}


class ContactHint(BaseModel):
    source: Source | None = None
    source_user_id: str | None = None
    display_name: str
    role: str | None = None
    company: str | None = None
    title: str | None = None
    phone_token: str | None = None
    email_token: str | None = None
    notes: str | None = None


class Deal(BaseModel):
    title: str
    counterparty_source: Source | None = None
    counterparty_user_id: str | None = None
    counterparty_hint: str | None = None
    stage: Stage = "lead"
    amount: float | None = None
    currency: str | None = None
    expected_close_date: str | None = None   # ISO yyyy-mm-dd
    evidence_message_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class ActionItem(BaseModel):
    owner_source: Source | None = None
    owner_user_id: str | None = None
    description: str
    due_date: str | None = None              # ISO yyyy-mm-dd
    source_message_id: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class Summary(BaseModel):
    source: Source
    thread_key: str
    window_start: int
    window_end: int
    bullet_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    deals: list[Deal] = Field(default_factory=list)
    contacts: list[ContactHint] = Field(default_factory=list)
    actions: list[ActionItem] = Field(default_factory=list)
    summary: Summary | None = None
