"""P0 HTTP smoke: signed input GET -> mock generation -> result PUT -> signed callback."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.main import app
from app.services.task_store import load_task_payload


SECRET = "p0-http-integration-secret"
EVENTS: list[tuple[str, dict]] = []
CALLBACKS: list[tuple[bytes, dict[str, str]]] = []
UPLOADED_RESULT = b""


def _png(width: int, height: int, color: tuple[int, int, int, int]) -> bytes:
    image = Image.new("RGBA", (width, height), color)
    ImageDraw.Draw(image).rectangle((2, 2, width - 3, height - 3), outline=(20, 40, 80, 255), width=2)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


PRODUCT = _png(96, 64, (220, 225, 230, 255))
LOGO = _png(32, 16, (210, 30, 30, 220))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        body = PRODUCT if path == "/product.png" else LOGO if path == "/logo.png" else None
        if body is None:
            self.send_error(404)
            return
        EVENTS.append(("get", {"path": path}))
        self.send_response(200)
        self.send_header("content-type", "image/png")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self) -> None:
        global UPLOADED_RESULT
        UPLOADED_RESULT = self.rfile.read(int(self.headers.get("content-length", "0")))
        EVENTS.append(("put", {"bytes": len(UPLOADED_RESULT), "content-type": self.headers.get("content-type")}))
        self.send_response(200)
        self.end_headers()

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        headers = {key.lower(): value for key, value in self.headers.items()}
        CALLBACKS.append((body, headers))
        EVENTS.append(("callback", json.loads(body)))
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


def _verify_callback(body: bytes, headers: dict[str, str]) -> None:
    timestamp = headers["x-ppe-callback-timestamp"]
    expected = "sha256=" + hmac.new(
        SECRET.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256
    ).hexdigest()
    assert hmac.compare_digest(expected, headers["x-ppe-callback-signature"])


def main() -> None:
    global UPLOADED_RESULT
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"
    test_root = PROJECT_ROOT / "storage" / "test_assets" / "p0_http_integration"

    original = {
        "input_dir": settings.input_dir,
        "output_dir": settings.output_dir,
        "task_dir": settings.task_dir,
        "ai_engine": settings.ai_engine,
        "storage_backend": settings.storage_backend,
        "ai_callback_secret": settings.ai_callback_secret,
        "callback_allowed_hosts": settings.callback_allowed_hosts,
        "asset_allowed_hosts": settings.asset_allowed_hosts,
    }
    settings.input_dir = test_root / "inputs"
    settings.output_dir = test_root / "outputs"
    settings.task_dir = test_root / "tasks"
    settings.ai_engine = "mock"
    settings.storage_backend = "local"
    settings.ai_callback_secret = SECRET
    settings.callback_allowed_hosts = "127.0.0.1"
    settings.asset_allowed_hosts = "127.0.0.1"

    job_id = "p0-http-integration"
    asset_key = f"results/smoke/{job_id}/attempt-0/result.png"
    try:
        payload = {
            "jobId": job_id,
            "type": "image_generation",
            "tenantId": "smoke",
            "traceId": "trace-p0-http-integration",
            "attempt": 0,
            "modelProfileId": "mock-p0",
            "workflowVersion": "mock-p0-v1",
            "inputAssets": [
                {
                    "assetId": "asset-product",
                    "role": "product_reference",
                    "version": 1,
                    "url": f"{base}/product.png?token=input-secret",
                },
                {
                    "assetId": "asset-logo",
                    "role": "logo",
                    "version": 1,
                    "url": f"{base}/logo.png?token=logo-secret",
                },
            ],
            "parameters": {
                "product_name": "P0 安全帽",
                "product_category": "头部防护/安全帽",
                "scene": "浅灰产品摄影背景",
                "style": "真实商业产品图",
                "size": "128x128",
                "output_format": "png",
                "sync": True,
            },
            "output": {
                "assetKey": asset_key,
                "uploadUrl": f"{base}/upload/result.png?token=upload-secret",
                "method": "PUT",
                "requiredHeaders": {"content-type": "image/png"},
            },
            "callback": f"{base}/callback",
        }
        response = TestClient(app).post("/ai/tasks", json=payload)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "succeeded", result
        assert result["result"]["assetKey"] == asset_key
        assert UPLOADED_RESULT.startswith(b"\x89PNG\r\n\x1a\n")

        assert len(CALLBACKS) >= 2
        for body, headers in CALLBACKS:
            _verify_callback(body, headers)
            event = json.loads(body)
            assert event["jobId"] == job_id
            assert event["attempt"] == 0
        assert json.loads(CALLBACKS[-1][0])["status"] == "succeeded"
        put_index = next(index for index, event in enumerate(EVENTS) if event[0] == "put")
        success_index = next(index for index, event in enumerate(EVENTS) if event[0] == "callback" and event[1]["status"] == "succeeded")
        assert put_index < success_index, "succeeded callback must occur after result PUT"

        stored = json.dumps(load_task_payload(job_id), ensure_ascii=False)
        for secret in ("input-secret", "logo-secret", "upload-secret"):
            assert secret not in stored
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        for name, value in original.items():
            setattr(settings, name, value)
        EVENTS.clear()
        CALLBACKS.clear()
        UPLOADED_RESULT = b""

    print("P0_HTTP_INTEGRATION_SMOKE_OK")


if __name__ == "__main__":
    main()
