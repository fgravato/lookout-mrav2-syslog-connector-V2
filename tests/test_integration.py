"""
Integration tests: SSE HTTP server -> MRAv2StreamThread -> EventForwarder.

Spins up a real in-process HTTP server to serve SSE events, mocks OAuth token
fetch, and asserts events flow end-to-end through the queue-based pipeline.
"""

import http.server
import json
import os
import requests
import socket
import sys
import threading
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.mra_v2_stream_thread import MRAv2StreamThread


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _sse_body(events: list, event_id: str = "test-uuid") -> bytes:
    payload = json.dumps({"events": events})
    return (
        f"event: events\nid: {event_id}\ndata: {payload}\n\n"
        "event: end\ndata: \n\n"
    ).encode()


def _run_sse_server(body: bytes) -> tuple:
    """Start a single-request SSE HTTP server. Returns (server, port)."""
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()

        def log_message(self, *a):
            pass

    port = _free_port()
    srv = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    return srv, port


def _make_thread(port: int, ent_name: str = "test-ent", forwarder=None) -> MRAv2StreamThread:
    """Build a stream thread pointed at a local HTTP server with OAuth mocked out."""
    if forwarder is None:
        forwarder = Mock()

    with patch("lookout_mra_client.mra_v2_stream.OAuth2Client") as mock_cls:
        mock_oauth = Mock()
        mock_oauth.session = requests.Session()
        mock_cls.return_value = mock_oauth

        thread = MRAv2StreamThread(
            ent_name=ent_name,
            event_forwarder=forwarder,
            api_domain=f"http://127.0.0.1:{port}",
            api_key="test-key",
            event_type="THREAT,DEVICE",
            timeout=5,
        )
    return thread


class TestIntegrationSSEPipeline:
    """Full pipeline: real HTTP SSE -> MRAv2StreamThread -> forwarder."""

    def test_events_flow_end_to_end(self):
        """Events from a live SSE endpoint reach the forwarder with the correct batch."""
        test_events = [
            {"type": "THREAT", "id": "t-1"},
            {"type": "DEVICE", "id": "d-2"},
        ]
        srv, port = _run_sse_server(_sse_body(test_events, event_id="abc-def"))
        forwarder = Mock()

        with patch("lookout_mra_client.mra_v2_stream.OAuth2Client") as mock_cls:
            mock_oauth = Mock()
            mock_oauth.session = requests.Session()
            mock_cls.return_value = mock_oauth

            thread = MRAv2StreamThread(
                ent_name="test-ent",
                event_forwarder=forwarder,
                api_domain=f"http://127.0.0.1:{port}",
                api_key="test-key",
                event_type="THREAT,DEVICE",
                timeout=5,
            )
            thread.run()

        srv.server_close()

        forwarder.write_all.assert_called_once()
        batch, ent = forwarder.write_all.call_args[0]
        assert len(batch) == 2
        assert ent == "test-ent"
        assert batch[0]["type"] == "THREAT"
        assert batch[1]["type"] == "DEVICE"

    def test_stream_position_updated_from_sse_id(self):
        """stream.last_event_id is updated to the id field from the SSE frame."""
        srv, port = _run_sse_server(
            _sse_body([{"type": "THREAT"}], event_id="position-uuid-42")
        )

        with patch("lookout_mra_client.mra_v2_stream.OAuth2Client") as mock_cls:
            mock_oauth = Mock()
            mock_oauth.session = requests.Session()
            mock_cls.return_value = mock_oauth

            thread = MRAv2StreamThread(
                ent_name="ent",
                event_forwarder=Mock(),
                api_domain=f"http://127.0.0.1:{port}",
                api_key="key",
                timeout=5,
            )
            thread.run()

        srv.server_close()
        assert thread.stream.last_event_id == "position-uuid-42"

    def test_invalid_json_drops_batch_without_crashing(self):
        """Malformed JSON in an SSE payload must not crash the thread."""
        body = (
            "event: events\nid: x\ndata: not-valid-json\n\n"
            "event: end\ndata: \n\n"
        ).encode()
        srv, port = _run_sse_server(body)
        forwarder = Mock()

        with patch("lookout_mra_client.mra_v2_stream.OAuth2Client") as mock_cls:
            mock_oauth = Mock()
            mock_oauth.session = requests.Session()
            mock_cls.return_value = mock_oauth

            thread = MRAv2StreamThread(
                ent_name="ent",
                event_forwarder=forwarder,
                api_domain=f"http://127.0.0.1:{port}",
                api_key="key",
                timeout=5,
            )
            thread.run()  # must not raise

        srv.server_close()
        forwarder.write_all.assert_not_called()

    def test_ent_name_passed_to_forwarder(self):
        """The entity name supplied to the thread reaches write_all."""
        srv, port = _run_sse_server(_sse_body([{"type": "AUDIT"}]))
        forwarder = Mock()

        with patch("lookout_mra_client.mra_v2_stream.OAuth2Client") as mock_cls:
            mock_oauth = Mock()
            mock_oauth.session = requests.Session()
            mock_cls.return_value = mock_oauth

            thread = MRAv2StreamThread(
                ent_name="my-specific-entity",
                event_forwarder=forwarder,
                api_domain=f"http://127.0.0.1:{port}",
                api_key="key",
                timeout=5,
            )
            thread.run()

        srv.server_close()
        _, ent = forwarder.write_all.call_args[0]
        assert ent == "my-specific-entity"

    def test_heartbeat_only_stream_does_not_call_forwarder(self):
        """A stream with only heartbeats (no data events) must not invoke write_all."""
        body = (
            "event: heartbeat\ndata: \n\n"
            "event: end\ndata: \n\n"
        ).encode()
        srv, port = _run_sse_server(body)
        forwarder = Mock()

        with patch("lookout_mra_client.mra_v2_stream.OAuth2Client") as mock_cls:
            mock_oauth = Mock()
            mock_oauth.session = requests.Session()
            mock_cls.return_value = mock_oauth

            thread = MRAv2StreamThread(
                ent_name="ent",
                event_forwarder=forwarder,
                api_domain=f"http://127.0.0.1:{port}",
                api_key="key",
                timeout=5,
            )
            thread.run()

        srv.server_close()
        forwarder.write_all.assert_not_called()
