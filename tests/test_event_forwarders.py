"""
Tests for event forwarders.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.event_forwarders.qradar_event_forwarder import QRadarEventForwarder
from lookout_mra_client.event_forwarders.splunk_event_forwarder import SplunkEventForwarder
from lookout_mra_client.event_forwarders.event_forwarder import EventForwarder


class TestEventForwarder:
    """Tests for base EventForwarder class."""
    
    def test_write_all_calls_write_for_each_event(self):
        """Test that write_all calls write for each event."""
        class TestForwarder(EventForwarder):
            def __init__(self):
                self.events = []
            
            def write(self, event, entName):
                self.events.append((event, entName))
        
        forwarder = TestForwarder()
        events = [{"id": 1}, {"id": 2}, {"id": 3}]
        
        forwarder.write_all(events, "test-company")
        
        assert len(forwarder.events) == 3
        assert forwarder.events[0][1] == "test-company"
    
    def test_write_not_implemented(self):
        """Test that base write method raises NotImplementedError."""
        forwarder = EventForwarder()
        
        with pytest.raises(NotImplementedError):
            forwarder.write({}, "test")


class TestQRadarEventForwarder:
    """Tests for QRadarEventForwarder class."""
    
    @pytest.fixture
    def forwarder(self):
        """Create a QRadar forwarder instance."""
        return QRadarEventForwarder(
            qradar_address=("localhost", 514),
            log_identifier_key="custom_key",
            log_identifier="custom_value",
            callback=None
        )
    
    def test_write_all_with_callback(self):
        """Test write_all with callback function."""
        callback_mock = Mock()
        forwarder = QRadarEventForwarder(
            qradar_address=("localhost", 514),
            log_identifier_key="",
            log_identifier="",
            callback=callback_mock
        )
        
        events = [{"type": "THREAT", "details": {"type": "THREAT"}}]
        
        with patch('lookout_mra_client.event_forwarders.qradar_event_forwarder.SyslogClient'):
            forwarder.write_all(events, "test-company")
        
        callback_mock.assert_called_once_with(events)
    
    def test_write_all_without_callback(self):
        """Test write_all without callback function (should not crash)."""
        forwarder = QRadarEventForwarder(
            qradar_address=("localhost", 514),
            log_identifier_key="",
            log_identifier="",
            callback=None
        )
        
        events = [{"type": "THREAT", "details": {"type": "THREAT"}}]
        
        # Should not raise TypeError
        with patch('lookout_mra_client.event_forwarders.qradar_event_forwarder.SyslogClient'):
            forwarder.write_all(events, "test-company")
    
    def test_log_identifier_added_to_events(self):
        """Test that log identifier is added to events."""
        forwarder = QRadarEventForwarder(
            qradar_address=("localhost", 514),
            log_identifier_key="custom_key",
            log_identifier="custom_value",
            callback=None
        )
        
        events = [{"type": "THREAT", "details": {"type": "THREAT"}}]
        
        with patch('lookout_mra_client.event_forwarders.qradar_event_forwarder.SyslogClient') as mock_client:
            forwarder.write_all(events, "test-company")
            
            # Check that write was called
            mock_client.return_value.write.assert_called()


class TestSplunkEventForwarder:
    """Tests for SplunkEventForwarder class."""
    
    @pytest.fixture
    def forwarder(self):
        """Create a Splunk forwarder instance."""
        return SplunkEventForwarder(callback=None)
    
    def test_write_outputs_json(self, forwarder, capsys):
        """Test that write outputs JSON to stdout."""
        event = {"id": 123, "type": "THREAT"}
        
        forwarder.write(event, "test-company")
        
        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        
        assert output["id"] == 123
        assert output["entName"] == "test-company"
        assert output["type"] == "THREAT"
    
    def test_write_adds_entName(self, forwarder, capsys):
        """Test that write adds entName to event."""
        event = {"id": 123}
        
        forwarder.write(event, "my-company")
        
        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        
        assert output["entName"] == "my-company"
    
    def test_write_defaults_type_to_unknown(self, forwarder, capsys):
        """Test that write defaults type to UNKNOWN if not present."""
        event = {"id": 123}
        
        forwarder.write(event, "test-company")
        
        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        
        assert output["type"] == "UNKNOWN"
    
    def test_write_all_with_callback(self, capsys):
        """Test write_all with callback."""
        callback_mock = Mock()
        forwarder = SplunkEventForwarder(callback=callback_mock)
        
        events = [{"id": 1}, {"id": 2}]
        forwarder.write_all(events, "test-company")
        
        callback_mock.assert_called_once_with(events)
        
        # Check that both events were written
        captured = capsys.readouterr()
        lines = captured.out.strip().split('\r\n')
        assert len(lines) == 2
    
    def test_write_all_without_callback(self, capsys):
        """Test write_all without callback (should not crash)."""
        forwarder = SplunkEventForwarder(callback=None)
        
        events = [{"id": 1}]
        
        # Should not raise TypeError
        forwarder.write_all(events, "test-company")
        
        captured = capsys.readouterr()
        assert "1" in captured.out
