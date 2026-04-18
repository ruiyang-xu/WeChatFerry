from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response

from ..base import Source as SourceBase
from .normalize import event_to_normalized

LOG = logging.getLogger(__name__)


class SlackSource(SourceBase):
    """Slack Events API webhook receiver.

    Verifies the `X-Slack-Signature` header via HMAC-SHA256 of
    `v0:<timestamp>:<raw_body>` using the signing secret, and responds to
    `url_verification` challenges.
    """

    def __init__(
        self,
        inbound,
        bind: str = "127.0.0.1",
        port: int = 8702,
        signing_secret_env: str = "SLACK_SIGNING_SECRET",
    ) -> None:
        super().__init__(inbound)
        self.bind = bind
        self.port = port
        self.signing_secret = os.environ.get(signing_secret_env, "").encode("utf-8")
        self._server_thread: threading.Thread | None = None
        self._server: Any | None = None
        self.app = self._build_app()

    def _verify(self, ts_header: str, signature: str, body: bytes) -> bool:
        if not self.signing_secret:
            return False
        try:
            ts_int = int(ts_header)
        except ValueError:
            return False
        if abs(int(time.time()) - ts_int) > 60 * 5:
            return False
        base = b"v0:" + ts_header.encode("utf-8") + b":" + body
        mac = hmac.new(self.signing_secret, base, hashlib.sha256).hexdigest()
        expected = f"v0={mac}"
        return hmac.compare_digest(expected, signature)

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.post("/webhook/slack")
        async def webhook(req: Request) -> Any:
            body = await req.body()
            ts = req.headers.get("x-slack-request-timestamp", "")
            sig = req.headers.get("x-slack-signature", "")
            if not self._verify(ts, sig, body):
                raise HTTPException(status_code=401, detail="invalid signature")
            import json
            payload = json.loads(body.decode("utf-8") or "{}")
            if payload.get("type") == "url_verification":
                return Response(content=payload.get("challenge", ""), media_type="text/plain")
            norm = event_to_normalized(payload)
            if norm is not None:
                self.emit(norm)
            return {"ok": True}

        return app

    def start(self) -> None:
        import uvicorn

        config = uvicorn.Config(self.app, host=self.bind, port=self.port, log_level="info")
        self._server = uvicorn.Server(config)
        self._server_thread = threading.Thread(
            target=self._server.run, name="slack-webhook", daemon=True
        )
        self._server_thread.start()
        LOG.info("Slack webhook listening on http://%s:%s/webhook/slack", self.bind, self.port)

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        self._server_thread = None
        self._server = None
