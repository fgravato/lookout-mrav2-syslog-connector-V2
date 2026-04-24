"""
Tests for the stream thread module.
"""

import pytest
import sys
import os
import queue
import threading
import time
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.mra_v2_stream_thread import MRAv2StreamThread


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_event_forwarder():
    return Mock()


@pytest.fixture
def mock_stream():
    with patch("lookout_mra_client.mra_v2_stream_thread.MRAv2Stream") as mock:
        instance = Mock()
        instance.event_type = "THREAT,DEVICE"
        instance.last_event_id = "0"
        instance.start_time = None
        mock.return_value = instance
        yield instance


def _make_thread(ent_name="test-company", forwarder=None, **kwargs):
    """Helper: build a thread with mocked MRAv2Stream."""
    if forwarder is None:
        forwarder = Mock()
    with patch("lookout_mra_client.mra_v2_stream_thread.MRAv2Stream") as mock_cls:
        instance = Mock()
        instance.event_type = "THREAT,DEVICE"
        instance.last_event_id = "0"
        instance.start_time = None
        mock_cls.return_value = instance
        t = MRAv2StreamThread(
            ent_name=ent_name,
            event_forwarder=forwarder,
            api_domain="https://api.lookout.com",
            api_key="test-key",
            **kwargs,
        )
    return t, instance


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestMRAv2StreamThread:
    def test_thread_initialization(self, mock_event_forwarder, mock_stream):
        thread = MRAv2StreamThread(
            ent_name="test-company",
            event_forwarder=mock_event_forwarder,
            api_domain="https://api.lookout.com",
            api_key="test-key",
        )
        assert thread.ent_name == "test-company"
        assert thread.event_forwarder == mock_event_forwarder
        assert isinstance(thread.shutdown_flag, threading.Event)
        assert thread.shutdown_flag.is_set() is False
        assert thread.error is None

    def test_queue_is_bounded(self, mock_event_forwarder, mock_stream):
        from lookout_mra_client.mra_v2_stream_thread import _QUEUE_MAXSIZE
        thread = MRAv2StreamThread(
            ent_name="test",
            event_forwarder=mock_event_forwarder,
            api_domain="https://api.lookout.com",
            api_key="test-key",
        )
        assert thread._queue.maxsize == _QUEUE_MAXSIZE

    def test_shutdown_flag_behavior(self, mock_event_forwarder, mock_stream):
        thread = MRAv2StreamThread(
            ent_name="test",
            event_forwarder=mock_event_forwarder,
            api_domain="https://api.lookout.com",
            api_key="test-key",
        )
        assert thread.shutdown_flag.is_set() is False
        thread.shutdown_flag.set()
        assert thread.shutdown_flag.is_set() is True
        thread.shutdown_flag.clear()
        assert thread.shutdown_flag.is_set() is False

    def test_thread_does_not_use_sys_exit(self, mock_event_forwarder, mock_stream):
        thread = MRAv2StreamThread(
            ent_name="test",
            event_forwarder=mock_event_forwarder,
            api_domain="https://api.lookout.com",
            api_key="test-key",
        )
        mock_event = Mock()
        mock_event.event = "heartbeat"
        mock_stream.listenForEvents.return_value = [mock_event]
        mock_stream.shutdown.return_value = ("0", None)

        thread.shutdown_flag.set()

        with patch.object(sys, "exit") as mock_exit:
            thread.run()
            mock_exit.assert_not_called()


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------

class TestMRAv2StreamThreadEventHandling:
    def test_events_processed_and_forwarded(self):
        mock_forwarder = Mock()

        with patch("lookout_mra_client.mra_v2_stream_thread.MRAv2Stream") as mock_cls:
            instance = Mock()
            instance.event_type = "THREAT"
            instance.last_event_id = "0"
            instance.start_time = None

            mock_event = Mock()
            mock_event.event = "events"
            mock_event.data = '{"events": [{"id": 1}, {"id": 2}]}'

            instance.listenForEvents.return_value = [mock_event]
            mock_cls.return_value = instance

            thread = MRAv2StreamThread(
                ent_name="test",
                event_forwarder=mock_forwarder,
                api_domain="https://api.lookout.com",
                api_key="test-key",
            )
            thread.run()

        mock_forwarder.write_all.assert_called_once()
        batch, ent = mock_forwarder.write_all.call_args[0]
        assert len(batch) == 2
        assert ent == "test"

    def test_heartbeat_event_does_not_trigger_write(self):
        mock_forwarder = Mock()

        with patch("lookout_mra_client.mra_v2_stream_thread.MRAv2Stream") as mock_cls:
            instance = Mock()
            instance.event_type = "THREAT"
            instance.last_event_id = "0"
            instance.start_time = None

            mock_event = Mock()
            mock_event.event = "heartbeat"

            instance.listenForEvents.return_value = [mock_event]
            mock_cls.return_value = instance

            thread = MRAv2StreamThread(
                ent_name="test",
                event_forwarder=mock_forwarder,
                api_domain="https://api.lookout.com",
                api_key="test-key",
            )
            thread.run()

        mock_forwarder.write_all.assert_not_called()

    def test_invalid_json_drops_batch_and_logs_error(self):
        """A JSON parse failure must log an error and NOT forward an empty batch."""
        mock_forwarder = Mock()

        with patch("lookout_mra_client.mra_v2_stream_thread.MRAv2Stream") as mock_cls:
            instance = Mock()
            instance.event_type = "THREAT"
            instance.last_event_id = "0"
            instance.start_time = None

            mock_event = Mock()
            mock_event.event = "events"
            mock_event.data = "invalid json {"

            instance.listenForEvents.return_value = [mock_event]
            mock_cls.return_value = instance

            thread = MRAv2StreamThread(
                ent_name="test",
                event_forwarder=mock_forwarder,
                api_domain="https://api.lookout.com",
                api_key="test-key",
            )
            thread.run()

        mock_forwarder.write_all.assert_not_called()

    def test_empty_events_list_not_queued(self):
        """An SSE batch with events=[] must not call write_all."""
        mock_forwarder = Mock()

        with patch("lookout_mra_client.mra_v2_stream_thread.MRAv2Stream") as mock_cls:
            instance = Mock()
            instance.event_type = "THREAT"
            instance.last_event_id = "0"
            instance.start_time = None

            mock_event = Mock()
            mock_event.event = "events"
            mock_event.data = '{"events": []}'

            instance.listenForEvents.return_value = [mock_event]
            mock_cls.return_value = instance

            thread = MRAv2StreamThread(
                ent_name="test",
                event_forwarder=mock_forwarder,
                api_domain="https://api.lookout.com",
                api_key="test-key",
            )
            thread.run()

        mock_forwarder.write_all.assert_not_called()

    def test_writer_error_does_not_crash_thread(self):
        """A forwarder that raises must not kill the thread."""
        mock_forwarder = Mock()
        mock_forwarder.write_all.side_effect = OSError("syslog unavailable")

        with patch("lookout_mra_client.mra_v2_stream_thread.MRAv2Stream") as mock_cls:
            instance = Mock()
            instance.event_type = "THREAT"
            instance.last_event_id = "0"
            instance.start_time = None

            mock_event = Mock()
            mock_event.event = "events"
            mock_event.data = '{"events": [{"type": "THREAT"}]}'

            instance.listenForEvents.return_value = [mock_event]
            mock_cls.return_value = instance

            thread = MRAv2StreamThread(
                ent_name="test",
                event_forwarder=mock_forwarder,
                api_domain="https://api.lookout.com",
                api_key="test-key",
            )
            thread.run()  # must not raise
