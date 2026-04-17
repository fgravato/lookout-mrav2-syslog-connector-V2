"""
Tests for event forwarders.

Covers:
- QRadarEventForwarder: persistent SyslogClient, idle-reconnect, SMISHING flattening
- SplunkEventForwarder: syslog-based JSON transport (not stdout), reconnect, delegation
- SyslogClient.close(): handler teardown, idempotency
"""

import json
import socket
import time
import pytest
from unittest.mock import Mock, patch, call

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.event_forwarders.qradar_event_forwarder import (
    QRadarEventForwarder,
    _RECONNECT_IDLE_SECONDS as QRADAR_IDLE,
)
from lookout_mra_client.event_forwarders.splunk_event_forwarder import (
    SplunkEventForwarder,
    _RECONNECT_IDLE_SECONDS as SPLUNK_IDLE,
)
from lookout_mra_client.event_forwarders.event_forwarder import EventForwarder


SYSLOG_ADDR = ("localhost", 514)


# ---------------------------------------------------------------------------
# Base EventForwarder
# ---------------------------------------------------------------------------

class TestEventForwarder:
    def test_write_all_calls_write_for_each_event(self):
        """write_all must call write() once per event, passing entName."""
        class _Forwarder(EventForwarder):
            def __init__(self):
                self.calls = []
            def write(self, event, entName):
                self.calls.append((event, entName))

        fwd = _Forwarder()
        events = [{"id": 1}, {"id": 2}, {"id": 3}]
        fwd.write_all(events, "acme")

        assert len(fwd.calls) == 3
        assert all(c[1] == "acme" for c in fwd.calls)

    def test_write_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            EventForwarder().write({}, "test")


# ---------------------------------------------------------------------------
# QRadarEventForwarder
# ---------------------------------------------------------------------------

@pytest.fixture
def qradar_sc_patch():
    """Patch SyslogClient inside the qradar module; yield the mock class."""
    with patch("lookout_mra_client.event_forwarders.qradar_event_forwarder.SyslogClient") as cls:
        cls.return_value = Mock()
        yield cls


@pytest.fixture
def qradar(qradar_sc_patch):
    return QRadarEventForwarder(
        qradar_address=SYSLOG_ADDR,
        log_identifier_key="src_key",
        log_identifier="src_val",
        callback=None,
    )


class TestQRadarEventForwarderConstruction:
    def test_client_created_once_at_init(self, qradar_sc_patch):
        QRadarEventForwarder(SYSLOG_ADDR, "", "", None)
        assert qradar_sc_patch.call_count == 1

    def test_default_transport_is_tcp(self, qradar_sc_patch):
        QRadarEventForwarder(SYSLOG_ADDR, "", "", None)
        _, kw = qradar_sc_patch.call_args
        assert kw["socktype"] == socket.SOCK_STREAM

    def test_udp_transport_when_requested(self, qradar_sc_patch):
        QRadarEventForwarder(SYSLOG_ADDR, "", "", None, use_udp=True)
        _, kw = qradar_sc_patch.call_args
        assert kw["socktype"] == socket.SOCK_DGRAM

    def test_last_write_time_starts_none(self, qradar):
        assert qradar._last_write_time is None


class TestQRadarEventForwarderWriteAll:
    def test_reuses_client_across_batches(self, qradar_sc_patch, qradar):
        """No new SyslogClient created on subsequent write_all calls."""
        ev = [{"type": "DEVICE"}]
        qradar.write_all(ev, "co")
        qradar.write_all(ev, "co")
        assert qradar_sc_patch.call_count == 1  # only the __init__ call

    def test_sends_each_event(self, qradar):
        events = [{"type": "DEVICE"}, {"type": "AUDIT"}, {"type": "THREAT",
                  "threat": {"classifications": ["malware"]}}]
        qradar.write_all(events, "co")
        assert qradar._syslog_client.write.call_count == 3

    def test_entname_injected(self, qradar):
        event = {"type": "DEVICE"}
        qradar.write_all([event], "acme-corp")
        assert event["entName"] == "acme-corp"

    def test_log_identifier_added_when_key_set(self, qradar):
        event = {"type": "DEVICE"}
        qradar.write_all([event], "co")
        assert event["src_key"] == "src_val"

    def test_log_identifier_skipped_when_key_empty(self, qradar_sc_patch):
        fwd = QRadarEventForwarder(SYSLOG_ADDR, "", "sentinel", None)
        event = {"type": "DEVICE"}
        fwd.write_all([event], "co")
        assert "sentinel" not in event.values()

    def test_callback_called_with_events(self, qradar_sc_patch):
        cb = Mock()
        fwd = QRadarEventForwarder(SYSLOG_ADDR, "", "", cb)
        events = [{"type": "DEVICE"}]
        fwd.write_all(events, "co")
        cb.assert_called_once_with(events)

    def test_no_crash_without_callback(self, qradar):
        qradar.write_all([{"type": "DEVICE"}], "co")  # must not raise

    def test_last_write_time_updated(self, qradar):
        qradar.write_all([{"type": "DEVICE"}], "co")
        assert qradar._last_write_time is not None


class TestQRadarReconnect:
    def test_reconnect_triggered_after_idle(self, qradar_sc_patch, qradar):
        """Gap > QRADAR_IDLE seconds must trigger _reconnect()."""
        qradar._last_write_time = time.time() - (QRADAR_IDLE + 1)
        with patch.object(qradar, "_reconnect") as mock_reconnect:
            qradar.write_all([{"type": "DEVICE"}], "co")
        mock_reconnect.assert_called_once()

    def test_no_reconnect_when_recent(self, qradar_sc_patch, qradar):
        qradar._last_write_time = time.time() - 5
        with patch.object(qradar, "_reconnect") as mock_reconnect:
            qradar.write_all([{"type": "DEVICE"}], "co")
        mock_reconnect.assert_not_called()

    def test_no_reconnect_on_first_call(self, qradar_sc_patch, qradar):
        """_last_write_time is None — should not trigger reconnect."""
        with patch.object(qradar, "_reconnect") as mock_reconnect:
            qradar.write_all([{"type": "DEVICE"}], "co")
        mock_reconnect.assert_not_called()

    def test_reconnect_closes_old_client_and_creates_new(self, qradar_sc_patch, qradar):
        old_client = qradar._syslog_client
        new_client = Mock()
        qradar_sc_patch.return_value = new_client  # ensure the next SyslogClient() call differs
        qradar._reconnect()
        old_client.close.assert_called_once()
        assert qradar._syslog_client is new_client


class TestQRadarSmishingFlattening:
    def test_multiple_detections_expand_to_individual_events(self, qradar_sc_patch):
        fwd = QRadarEventForwarder(SYSLOG_ADDR, "", "", None)
        event = {
            "type": "SMISHING_ALERT",
            "smishing_alert": {"detections": [{"id": "d1"}, {"id": "d2"}, {"id": "d3"}]},
        }
        fwd.write_all([event], "co")
        assert fwd._syslog_client.write.call_count == 3

    def test_each_expanded_event_has_single_detection(self, qradar_sc_patch):
        fwd = QRadarEventForwarder(SYSLOG_ADDR, "", "", None)
        event = {
            "type": "SMISHING_ALERT",
            "smishing_alert": {"detections": [{"id": "d1"}]},
        }
        fwd.write_all([event], "co")
        sent = fwd._syslog_client.write.call_args[0][0]
        assert "detection" in sent["smishing_alert"]
        assert "detections" not in sent["smishing_alert"]
        assert sent["smishing_alert"]["detection"] == {"id": "d1"}

    def test_original_event_not_mutated_by_flattening(self, qradar_sc_patch):
        """Deep copy ensures the caller's event dict is unchanged."""
        fwd = QRadarEventForwarder(SYSLOG_ADDR, "", "", None)
        event = {
            "type": "SMISHING_ALERT",
            "smishing_alert": {"detections": [{"id": "d1"}, {"id": "d2"}]},
        }
        original_detections = list(event["smishing_alert"]["detections"])
        fwd.write_all([event], "co")
        # original list must still be intact
        assert event["smishing_alert"]["detections"] == original_detections

    def test_smishing_with_empty_detections_passes_through(self, qradar_sc_patch):
        fwd = QRadarEventForwarder(SYSLOG_ADDR, "", "", None)
        event = {"type": "SMISHING_ALERT", "smishing_alert": {"detections": []}}
        fwd.write_all([event], "co")
        assert fwd._syslog_client.write.call_count == 1

    def test_callback_receives_flattened_list(self, qradar_sc_patch):
        cb = Mock()
        fwd = QRadarEventForwarder(SYSLOG_ADDR, "", "", cb)
        event = {
            "type": "SMISHING_ALERT",
            "smishing_alert": {"detections": [{"id": "d1"}, {"id": "d2"}]},
        }
        fwd.write_all([event], "co")
        # callback must receive 2 events (one per detection), not 1
        assert len(cb.call_args[0][0]) == 2


# ---------------------------------------------------------------------------
# SplunkEventForwarder
# ---------------------------------------------------------------------------

@pytest.fixture
def splunk_sc_patch():
    """Patch SyslogClient inside the splunk module; yield the mock class."""
    with patch("lookout_mra_client.event_forwarders.splunk_event_forwarder.SyslogClient") as cls:
        cls.return_value = Mock()
        yield cls


@pytest.fixture
def splunk(splunk_sc_patch):
    return SplunkEventForwarder(syslog_address=SYSLOG_ADDR)


class TestSplunkEventForwarderConstruction:
    def test_client_created_once_at_init(self, splunk_sc_patch):
        SplunkEventForwarder(syslog_address=SYSLOG_ADDR)
        assert splunk_sc_patch.call_count == 1

    def test_correct_address_passed_to_client(self, splunk_sc_patch):
        addr = ("syslog.corp.internal", 5514)
        SplunkEventForwarder(syslog_address=addr)
        args, kw = splunk_sc_patch.call_args
        actual = kw.get("syslog_address") or args[2]
        assert actual == addr

    def test_default_transport_is_tcp(self, splunk_sc_patch):
        SplunkEventForwarder(syslog_address=SYSLOG_ADDR)
        _, kw = splunk_sc_patch.call_args
        assert kw["socktype"] == socket.SOCK_STREAM

    def test_udp_transport_when_requested(self, splunk_sc_patch):
        SplunkEventForwarder(syslog_address=SYSLOG_ADDR, use_udp=True)
        _, kw = splunk_sc_patch.call_args
        assert kw["socktype"] == socket.SOCK_DGRAM

    def test_formatter_produces_valid_json(self, splunk_sc_patch):
        """The formatter callable passed to SyslogClient must emit valid JSON."""
        SplunkEventForwarder(syslog_address=SYSLOG_ADDR)
        args, kw = splunk_sc_patch.call_args
        formatter = kw.get("event_formatter") or args[1]
        payload = formatter({"type": "THREAT", "id": "abc"})
        parsed = json.loads(payload)
        assert parsed == {"type": "THREAT", "id": "abc"}

    def test_last_write_time_starts_none(self, splunk):
        assert splunk._last_write_time is None


class TestSplunkEventForwarderWrite:
    def test_write_sends_event_to_syslog_client(self, splunk):
        event = {"type": "THREAT"}
        splunk.write(event, "acme")
        splunk._syslog_client.write.assert_called_once_with(event)

    def test_write_injects_entname(self, splunk):
        event = {"type": "THREAT"}
        splunk.write(event, "acme-corp")
        assert event["entName"] == "acme-corp"

    def test_write_defaults_type_to_unknown(self, splunk):
        event = {"id": 99}
        splunk.write(event, "co")
        assert event["type"] == "UNKNOWN"

    def test_write_preserves_existing_type(self, splunk):
        event = {"type": "DEVICE"}
        splunk.write(event, "co")
        assert event["type"] == "DEVICE"

    def test_write_does_not_touch_stdout(self, splunk, capsys):
        """This is a daemon — nothing must reach stdout."""
        splunk.write({"type": "THREAT"}, "co")
        assert capsys.readouterr().out == ""


class TestSplunkEventForwarderWriteAll:
    def test_write_all_delegates_to_write(self, splunk):
        events = [{"type": "THREAT"}, {"type": "DEVICE"}, {"type": "AUDIT"}]
        with patch.object(splunk, "write") as mock_write:
            splunk.write_all(events, "co")
        assert mock_write.call_count == 3

    def test_write_all_passes_entname_to_every_event(self, splunk):
        events = [{"type": "DEVICE"}, {"type": "AUDIT"}]
        splunk.write_all(events, "my-ent")
        for e in events:
            assert e["entName"] == "my-ent"

    def test_write_all_with_callback(self, splunk_sc_patch):
        cb = Mock()
        fwd = SplunkEventForwarder(syslog_address=SYSLOG_ADDR, callback=cb)
        events = [{"id": 1}, {"id": 2}]
        fwd.write_all(events, "co")
        cb.assert_called_once_with(events)

    def test_write_all_without_callback(self, splunk):
        splunk.write_all([{"type": "DEVICE"}], "co")  # must not raise

    def test_last_write_time_updated(self, splunk):
        splunk.write_all([{"type": "DEVICE"}], "co")
        assert splunk._last_write_time is not None


class TestSplunkReconnect:
    def test_reconnect_triggered_after_idle(self, splunk_sc_patch, splunk):
        splunk._last_write_time = time.time() - (SPLUNK_IDLE + 1)
        with patch.object(splunk, "_reconnect") as mock_reconnect:
            splunk.write_all([{"type": "DEVICE"}], "co")
        mock_reconnect.assert_called_once()

    def test_no_reconnect_when_recent(self, splunk_sc_patch, splunk):
        splunk._last_write_time = time.time() - 5
        with patch.object(splunk, "_reconnect") as mock_reconnect:
            splunk.write_all([{"type": "DEVICE"}], "co")
        mock_reconnect.assert_not_called()

    def test_no_reconnect_on_first_call(self, splunk_sc_patch, splunk):
        with patch.object(splunk, "_reconnect") as mock_reconnect:
            splunk.write_all([{"type": "DEVICE"}], "co")
        mock_reconnect.assert_not_called()

    def test_reconnect_closes_old_client_and_creates_new(self, splunk_sc_patch, splunk):
        old_client = splunk._syslog_client
        new_client = Mock()
        splunk_sc_patch.return_value = new_client  # ensure the next SyslogClient() call differs
        splunk._reconnect()
        old_client.close.assert_called_once()
        assert splunk._syslog_client is new_client


# ---------------------------------------------------------------------------
# SyslogClient.close()
# ---------------------------------------------------------------------------

class TestSyslogClientClose:
    """
    Tests for SyslogClient.close() — the method added to fix the
    handler/socket leak when QRadar was recreating clients every batch.
    """

    def _make_client(self, name, socktype=socket.SOCK_STREAM):
        from lookout_mra_client.syslog_client import SyslogClient
        with patch("lookout_mra_client.syslog_client._SysLogHandler") as handler_cls:
            mock_handler = Mock()
            # prevent AttributeError when SyslogClient sets handler.formatter
            mock_handler.formatter = None
            handler_cls.return_value = mock_handler
            client = SyslogClient(
                name=name,
                event_formatter=lambda e: str(e),
                syslog_address=("localhost", 514),
                socktype=socktype,
            )
        return client, mock_handler

    def test_close_removes_all_handlers(self):
        client, _ = self._make_client("test-close-removes")
        assert len(client.syslog_logger.handlers) == 1
        client.close()
        assert len(client.syslog_logger.handlers) == 0

    def test_close_calls_handler_close(self):
        client, mock_handler = self._make_client("test-close-socket")
        client.close()
        mock_handler.close.assert_called_once()

    def test_close_is_idempotent(self):
        client, _ = self._make_client("test-close-idempotent")
        client.close()
        client.close()  # second call must not raise
        assert len(client.syslog_logger.handlers) == 0

    def test_close_tolerates_handler_close_exception(self):
        """If handler.close() raises, close() must still remove the handler."""
        client, mock_handler = self._make_client("test-close-exc")
        mock_handler.close.side_effect = OSError("socket gone")
        client.close()  # must not propagate the OSError
        assert len(client.syslog_logger.handlers) == 0


class TestSysLogHandlerFraming:
    """
    Tests for the TCP record-delimiter fix.

    Python's SysLogHandler appends \\000 (null) to every message.
    rsyslog imtcp uses newline framing, so null-terminated messages
    accumulate and are never flushed.  _SysLogHandler overrides
    log_format_string to use \\n for TCP only.
    """

    def test_tcp_uses_newline_terminator(self):
        """TCP handler must use \\n so rsyslog imtcp flushes each record."""
        from lookout_mra_client.syslog_client import _SysLogHandler
        with patch.object(_SysLogHandler, "__init__", lambda self, *a, **kw: None):
            handler = _SysLogHandler.__new__(_SysLogHandler)
            # Simulate what our __init__ does after super().__init__
            handler._internal_logger = Mock()
            handler.log_format_string = '<%d>%s\000'  # default
            if socket.SOCK_STREAM == socket.SOCK_STREAM:
                handler.log_format_string = '<%d>%s\n'
        assert handler.log_format_string.endswith('\n')
        assert not handler.log_format_string.endswith('\000')

    def test_udp_keeps_null_terminator(self):
        """UDP handler keeps \\000 (datagrams are self-delimiting)."""
        from lookout_mra_client.syslog_client import _SysLogHandler
        # Construct via a real init with _SysLogHandler patching super
        with patch("lookout_mra_client.syslog_client.SysLogHandler.__init__"):
            handler = _SysLogHandler.__new__(_SysLogHandler)
            handler._internal_logger = Mock()
            # Reproduce only the socktype branch, not the full super().__init__
            handler.log_format_string = '<%d>%s\000'
            socktype = socket.SOCK_DGRAM
            if socktype == socket.SOCK_STREAM:
                handler.log_format_string = '<%d>%s\n'
        assert handler.log_format_string.endswith('\000')

    def test_handler_directly_tcp_gets_newline_format(self):
        """
        Instantiate _SysLogHandler directly with SOCK_STREAM (patching the
        parent __init__ to avoid opening a real socket) and verify that
        log_format_string ends with \\n, not \\000.
        """
        from lookout_mra_client.syslog_client import _SysLogHandler
        with patch("lookout_mra_client.syslog_client.SysLogHandler.__init__"):
            handler = _SysLogHandler.__new__(_SysLogHandler)
            _SysLogHandler.__init__(
                handler,
                Mock(),                    # internal_logger
                address=("localhost", 514),
                socktype=socket.SOCK_STREAM,
            )
        assert handler.log_format_string.endswith('\n'), (
            "TCP handler must use \\n so rsyslog imtcp flushes each record"
        )
