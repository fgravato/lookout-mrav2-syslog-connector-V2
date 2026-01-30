"""
Tests for the stream thread module.
"""

import pytest
import sys
import os
import threading
import time
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.mra_v2_stream_thread import MRAv2StreamThread


class TestMRAv2StreamThread:
    """Tests for MRAv2StreamThread class."""
    
    @pytest.fixture
    def mock_event_forwarder(self):
        """Create a mock event forwarder."""
        return Mock()
    
    @pytest.fixture
    def mock_stream(self):
        """Create a mock MRA stream."""
        with patch('lookout_mra_client.mra_v2_stream_thread.MRAv2Stream') as mock:
            stream_instance = Mock()
            stream_instance.event_type = "THREAT,DEVICE"
            stream_instance.last_event_id = 0
            stream_instance.start_time = None
            mock.return_value = stream_instance
            yield stream_instance
    
    def test_thread_initialization(self, mock_event_forwarder, mock_stream):
        """Test that thread initializes correctly."""
        thread = MRAv2StreamThread(
            entName="test-company",
            eventForwarder=mock_event_forwarder,
            api_domain="https://api.lookout.com",
            api_key="test-key"
        )
        
        assert thread.ent_name == "test-company"
        assert thread.event_forwarder == mock_event_forwarder
        assert isinstance(thread.shutdown_flag, threading.Event)
        assert thread.shutdown_flag.is_set() is False
        assert thread.error is None
    
    def test_shutdown_flag_behavior(self, mock_event_forwarder, mock_stream):
        """Test that shutdown flag works correctly."""
        thread = MRAv2StreamThread(
            entName="test",
            eventForwarder=mock_event_forwarder,
            api_domain="https://api.lookout.com",
            api_key="test-key"
        )
        
        # Initially not set
        assert thread.shutdown_flag.is_set() is False
        
        # Set the flag
        thread.shutdown_flag.set()
        assert thread.shutdown_flag.is_set() is True
        
        # Clear the flag
        thread.shutdown_flag.clear()
        assert thread.shutdown_flag.is_set() is False
    
    def test_thread_does_not_use_sys_exit(self, mock_event_forwarder, mock_stream):
        """Test that thread doesn't call sys.exit() on shutdown."""
        # Create a thread with mocked stream that yields one event then we set shutdown
        thread = MRAv2StreamThread(
            entName="test",
            eventForwarder=mock_event_forwarder,
            api_domain="https://api.lookout.com",
            api_key="test-key"
        )
        
        # Mock the stream to return an event then stop
        mock_event = Mock()
        mock_event.event = "heartbeat"
        mock_stream.listenForEvents.return_value = [mock_event]
        
        # Set shutdown flag before running
        thread.shutdown_flag.set()
        
        # Mock stream.shutdown to verify it's called
        mock_stream.shutdown.return_value = (0, None)
        
        # Run should complete without calling sys.exit()
        # If sys.exit() is called, this would raise SystemExit
        with patch.object(sys, 'exit') as mock_exit:
            thread.run()
            mock_exit.assert_not_called()


class TestMRAv2StreamThreadEventHandling:
    """Tests for event handling in MRAv2StreamThread."""
    
    def test_events_processed_and_forwarded(self):
        """Test that events are processed and forwarded."""
        mock_forwarder = Mock()
        
        with patch('lookout_mra_client.mra_v2_stream_thread.MRAv2Stream') as mock_stream_class:
            stream_instance = Mock()
            stream_instance.event_type = "THREAT"
            stream_instance.last_event_id = 0
            stream_instance.start_time = None
            
            # Create mock events
            mock_event = Mock()
            mock_event.event = "events"
            mock_event.data = '{"events": [{"id": 1}, {"id": 2}]}'
            
            stream_instance.listenForEvents.return_value = [mock_event]
            mock_stream_class.return_value = stream_instance
            
            thread = MRAv2StreamThread(
                entName="test",
                eventForwarder=mock_forwarder,
                api_domain="https://api.lookout.com",
                api_key="test-key"
            )
            
            # Don't actually run the thread, just call run directly
            thread.run()
            
            # Verify events were forwarded
            mock_forwarder.write_all.assert_called_once()
            args = mock_forwarder.write_all.call_args
            assert len(args[0][0]) == 2  # Two events
            assert args[0][1] == "test"  # entName
    
    def test_heartbeat_event_handling(self):
        """Test that heartbeat events are handled correctly."""
        mock_forwarder = Mock()
        
        with patch('lookout_mra_client.mra_v2_stream_thread.MRAv2Stream') as mock_stream_class:
            stream_instance = Mock()
            stream_instance.event_type = "THREAT"
            stream_instance.last_event_id = 0
            stream_instance.start_time = None
            
            mock_event = Mock()
            mock_event.event = "heartbeat"
            
            stream_instance.listenForEvents.return_value = [mock_event]
            mock_stream_class.return_value = stream_instance
            
            thread = MRAv2StreamThread(
                entName="test",
                eventForwarder=mock_forwarder,
                api_domain="https://api.lookout.com",
                api_key="test-key"
            )
            
            thread.run()
            
            # Heartbeats should not trigger write_all
            mock_forwarder.write_all.assert_not_called()
    
    def test_invalid_json_handling(self):
        """Test handling of invalid JSON in event data."""
        mock_forwarder = Mock()
        
        with patch('lookout_mra_client.mra_v2_stream_thread.MRAv2Stream') as mock_stream_class:
            stream_instance = Mock()
            stream_instance.event_type = "THREAT"
            stream_instance.last_event_id = 0
            stream_instance.start_time = None
            
            mock_event = Mock()
            mock_event.event = "events"
            mock_event.data = 'invalid json {'
            
            stream_instance.listenForEvents.return_value = [mock_event]
            mock_stream_class.return_value = stream_instance
            
            thread = MRAv2StreamThread(
                entName="test",
                eventForwarder=mock_forwarder,
                api_domain="https://api.lookout.com",
                api_key="test-key"
            )
            
            # Should not raise exception
            thread.run()
            
            # Should write empty list when JSON is invalid
            mock_forwarder.write_all.assert_called_once_with([], "test")
