from __future__ import annotations

from .schemas import ExtractionResult

SYSTEM_PROMPT = """You are an extraction engine for a sales CRM. Given a chat transcript, return a single JSON object that matches the provided JSON Schema exactly.

Rules:
- Only include fields for which you have direct textual evidence.
- Never invent numeric amounts. If an amount is unclear, omit `amount`.
- Use ISO dates (YYYY-MM-DD) if you can infer them from context; otherwise omit.
- `evidence_message_ids` and `source_message_id` must be real message ids from the transcript.
- Treat tokens like <<PHONE_1>>, <<EMAIL_2>>, <<CN_ID_1>>, <<BANK_1>> as opaque placeholders. Do not try to decode or reverse them.
- If the transcript is too sparse to extract anything, return an object with empty arrays and no summary.
- Output JSON only. No prose."""


FEW_SHOT_GROUP = """Example transcript:
[1712000000] alice (msg_1): We're interested in the annual plan at ~$20k, can you send a proposal?
[1712000100] bob (msg_2): Yes, I'll send it by Friday. Also let's loop in <<EMAIL_1>>.

Example JSON output:
{"deals":[{"title":"Annual plan","counterparty_hint":"alice","stage":"proposal","amount":20000,"currency":"USD","evidence_message_ids":["msg_1","msg_2"],"confidence":0.8}],"contacts":[{"display_name":"alice","role":"buyer"},{"display_name":"bob","role":"seller","email_token":"<<EMAIL_1>>"}],"actions":[{"description":"Send proposal to alice","owner_user_id":"bob","due_date":null,"source_message_id":"msg_2","confidence":0.85}],"summary":{"source":"wechat","thread_key":"room_123","window_start":1712000000,"window_end":1712000100,"bullet_points":["alice interested in annual plan","bob to send proposal by Friday"],"decisions":[],"open_questions":[]}}"""


def build_user_prompt(transcript: str, source: str, thread_key: str) -> str:
    schema_json = ExtractionResult.model_json_schema()
    import json as _json
    return (
        f"Source: {source}\nThread: {thread_key}\n\n"
        f"JSON Schema the output must match:\n{_json.dumps(schema_json)}\n\n"
        f"{FEW_SHOT_GROUP}\n\n"
        f"Now extract from this transcript:\n{transcript}\n\nReturn JSON only."
    )
