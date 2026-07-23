"""End-to-end scan test against a fake Anthropic API.

Unlike the other discovery tests (which stub out ``_create_message``),
this exercises the REAL path — the anthropic SDK's streaming client, the
SSE protocol, the background job, parsing, and the polling endpoint —
against a local server that speaks the Messages API stream format. It
exists because the streaming layer is exactly where production failures
lived, and stubbing it hid them.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

SUGGESTION_TEXT = """Here is what I found.

```json
[
  {
    "name": "La Chope des Puces",
    "type": "bar",
    "city": "Saint-Ouen",
    "country": "France",
    "website": "https://www.lachopedespuces.fr",
    "artist": "Rhythm Future Quartet",
    "source_url": "https://example.com/gig"
  }
]
```"""


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode()


class FakeClaude(BaseHTTPRequestHandler):
    """Speaks just enough of the Messages API stream format for one turn."""

    def do_POST(self):  # noqa: N802 — http.server naming
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()

        w = self.wfile.write
        w(
            _sse(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg_fake",
                        "type": "message",
                        "role": "assistant",
                        "model": "claude-opus-4-8",
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 100, "output_tokens": 1},
                    },
                },
            )
        )
        # A server-side web search block, as the real tool emits
        w(
            _sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "server_tool_use",
                        "id": "srvtoolu_fake",
                        "name": "web_search",
                        "input": {},
                    },
                },
            )
        )
        w(_sse("content_block_stop", {"type": "content_block_stop", "index": 0}))
        # The final text with the JSON fence
        w(
            _sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 1,
                    "content_block": {"type": "text", "text": ""},
                },
            )
        )
        w(
            _sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "text_delta", "text": SUGGESTION_TEXT},
                },
            )
        )
        w(_sse("content_block_stop", {"type": "content_block_stop", "index": 1}))
        w(
            _sse(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 500},
                },
            )
        )
        w(_sse("message_stop", {"type": "message_stop"}))

    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture()
def fake_claude(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeClaude)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv(
        "ANTHROPIC_BASE_URL", f"http://127.0.0.1:{server.server_address[1]}"
    )
    yield server
    server.shutdown()


def test_full_scan_against_fake_claude(auth_client, fake_claude):
    started = auth_client.post(
        "/api/discovery", json={"artists": ["Rhythm Future Quartet"]}
    )
    assert started.status_code == 202
    job = auth_client.get(
        f"/api/discovery/jobs/{started.json()['job_id']}"
    ).json()

    assert job["status"] == "done", job["error"]
    # Progress notes were emitted along the way
    assert job["note"] is not None
    names = [s["name"] for s in job["suggestions"]]
    assert names == ["La Chope des Puces"]
    suggestion = job["suggestions"][0]
    assert suggestion["type"] == "bar"
    assert suggestion["artist"] == "Rhythm Future Quartet"
