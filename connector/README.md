# connector

Standalone Python connector that ingests live conversations from **WeChat** (via WeChatFerry/pyauto), **Feishu**, and **Slack**, extracts CRM entities (deals, contacts, action items, summaries) using a local LLM, and stages them in a local SQLite database for a downstream dashboard (e.g. Secondaries).

## Data sovereignty

- Zero external egress by default. Local Ollama is the default LLM.
- Optional external LLM is fail-closed: disabled unless the user explicitly enables it, enforces PII redaction, requires a non-empty domain allowlist, and writes every call to an append-only `egress_log` table.
- SQLite lives locally; no network push in v1.
- The Secondaries exporter is defined as an interface only in v1; no implementation ships.

## Quick start

```bash
pip install -e .
ollama serve && ollama pull qwen2.5:7b-instruct
cp config/connector.yaml ./connector.yaml   # edit sources.*.enabled
connector doctor
connector run --source wechat
```

## Architecture

See `/root/.claude/plans/i-want-to-build-steady-hamster.md` for the full plan. Short version:

```
[WeChat via wcferry] ─┐
[Feishu webhook]   ───┼─► NormalizedMsg ─► BatchWorker ─► ConversationWindow
[Slack webhook]    ───┘                                         │ flush
                                                                ▼
                                     redact ─► LLM (Ollama default) ─► rehydrate
                                                                │
                                                                ▼
                                             resolver upserts to SQLite
                                                                │
                                              (v2) Exporter ─► Secondaries
```
