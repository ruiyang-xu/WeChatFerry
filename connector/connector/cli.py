from __future__ import annotations

import argparse
import logging
import queue
import signal
import sys
import time
from pathlib import Path

from .config import ConfigError, load as load_config
from .exporters.base import NoopExporter
from .llm.router import LlmRouter
from .pipeline import Pipeline
from .redact import PiiRedactor
from .schemas import NormalizedMsg
from .storage.db import WriteHandle, connect
from .storage.resolver import Resolver
from .windowing import WindowStore
from .workers import BatchWorker

LOG = logging.getLogger("connector")


def _build_runtime(cfg_path: str):
    cfg = load_config(cfg_path)
    conn = connect(cfg.storage.db_path)
    wh = WriteHandle(conn)
    router = LlmRouter.from_config(cfg)
    resolver = Resolver(wh)
    pipeline = Pipeline(wh=wh, router=router, resolver=resolver, redactor=PiiRedactor(), exporter=NoopExporter())
    store = WindowStore(
        max_messages=cfg.windowing.max_messages,
        idle_seconds=cfg.windowing.idle_seconds,
        max_wall_minutes=cfg.windowing.max_wall_minutes,
    )
    inbound: "queue.Queue[NormalizedMsg]" = queue.Queue(maxsize=10000)
    worker = BatchWorker(inbound=inbound, store=store, pipeline=pipeline)
    return cfg, inbound, worker


def _start_sources(cfg, inbound, selected: str):
    sources = []
    want_all = selected == "all"
    if (want_all or selected == "wechat") and cfg.sources.wechat.enabled:
        from .sources.wechat.adapter import WeChatSource
        src = WeChatSource(
            inbound=inbound,
            host=cfg.sources.wechat.wcferry_host,
            port=cfg.sources.wechat.wcferry_port,
        )
        src.start()
        sources.append(src)
    if (want_all or selected == "feishu") and cfg.sources.feishu.enabled:
        from .sources.feishu.webhook import FeishuSource
        src = FeishuSource(
            inbound=inbound,
            bind=cfg.sources.feishu.bind,
            port=cfg.sources.feishu.port,
            verification_token_env=cfg.sources.feishu.verification_token_env,
            encrypt_key_env=cfg.sources.feishu.encrypt_key_env,
        )
        src.start()
        sources.append(src)
    if (want_all or selected == "slack") and cfg.sources.slack.enabled:
        from .sources.slack.webhook import SlackSource
        src = SlackSource(
            inbound=inbound,
            bind=cfg.sources.slack.bind,
            port=cfg.sources.slack.port,
            signing_secret_env=cfg.sources.slack.signing_secret_env,
        )
        src.start()
        sources.append(src)
    return sources


def cmd_run(args: argparse.Namespace) -> int:
    cfg, inbound, worker = _build_runtime(args.config)
    worker.start()
    sources = _start_sources(cfg, inbound, args.source)
    if not sources:
        LOG.error("no sources enabled for selection %r; edit %s", args.source, args.config)
        worker.stop()
        return 2

    stop = {"flag": False}

    def _sig(*_):
        stop["flag"] = True
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    LOG.info("connector running; Ctrl-C to stop")
    try:
        while not stop["flag"]:
            time.sleep(0.5)
    finally:
        for s in sources:
            try:
                s.stop()
            except Exception:
                LOG.exception("source stop failed")
        worker.stop(drain=True)
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    connect(cfg.storage.db_path)
    LOG.info("migrated %s", cfg.storage.db_path)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"CONFIG: FAIL — {exc}")
        return 1
    print(f"CONFIG: ok ({args.config})")

    db = Path(cfg.storage.db_path)
    try:
        connect(cfg.storage.db_path)
        print(f"DB: ok ({db})")
    except Exception as exc:
        print(f"DB: FAIL — {exc}")
        return 1

    try:
        import httpx
        r = httpx.get(cfg.local_llm.endpoint.rstrip("/") + "/api/tags", timeout=3)
        r.raise_for_status()
        print(f"OLLAMA: reachable at {cfg.local_llm.endpoint}")
    except Exception as exc:
        print(f"OLLAMA: unreachable ({exc})  — local LLM required for extraction")
        return 1

    if cfg.external_llm.enabled:
        print(f"EXTERNAL_LLM: enabled (allow_domains={cfg.external_llm.allow_domains})")
    else:
        print("EXTERNAL_LLM: disabled (data stays local)")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="connector", description="Conversation -> CRM connector")
    parser.add_argument("--config", default="./connector.yaml", help="path to connector.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run enabled sources")
    p_run.add_argument("--source", choices=["all", "wechat", "feishu", "slack"], default="all")
    p_run.set_defaults(func=cmd_run)

    p_mig = sub.add_parser("migrate", help="run schema migrations")
    p_mig.set_defaults(func=cmd_migrate)

    p_doc = sub.add_parser("doctor", help="validate config + probe dependencies")
    p_doc.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
