from __future__ import annotations

import logging
import os
import threading
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from ..base import Source as SourceBase
from .normalize import event_to_normalized

LOG = logging.getLogger(__name__)


class FeishuSource(SourceBase):
    """Feishu Open Platform webhook receiver.

    Verifies the `verification_token` and handles both the url_verification
    challenge and event_callback payloads. Encrypted payloads (AES) are out of
    scope for v1 — operators should disable encryption or land a v1.1 adapter.
    """

    def __init__(
        self,
        inbound,
        bind: str = "127.0.0.1",
        port: int = 8701,
        verification_token_env: str = "FEISHU_VERIFICATION_TOKEN",
        encrypt_key_env: str = "FEISHU_ENCRYPT_KEY",
    ) -> None:
        super().__init__(inbound)
        self.bind = bind
        self.port = port
        self.verification_token = os.environ.get(verification_token_env, "")
        self.encrypt_key = os.environ.get(encrypt_key_env, "")
        self._server_thread: threading.Thread | None = None
        self._server: Any | None = None
        self.app = self._build_app()

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.post("/webhook/feishu")
        async def webhook(req: Request) -> dict:
            body = await req.json()
            if body.get("encrypt"):
                raise HTTPException(status_code=400, detail="encrypted payloads unsupported in v1")
            token = body.get("token") or (body.get("header") or {}).get("token") or ""
            if self.verification_token and token != self.verification_token:
                raise HTTPException(status_code=401, detail="invalid verification token")
            if body.get("type") == "url_verification":
                return {"challenge": body.get("challenge", "")}
            norm = event_to_normalized(body)
            if norm is not None:
                self.emit(norm)
            return {"ok": True}

        return app

    def start(self) -> None:
        import uvicorn

        config = uvicorn.Config(self.app, host=self.bind, port=self.port, log_level="info")
        self._server = uvicorn.Server(config)
        self._server_thread = threading.Thread(
            target=self._server.run, name="feishu-webhook", daemon=True
        )
        self._server_thread.start()
        LOG.info("Feishu webhook listening on http://%s:%s/webhook/feishu", self.bind, self.port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        self._server_thread = None
        self._server = None
