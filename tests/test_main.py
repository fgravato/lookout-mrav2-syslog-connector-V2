"""
Tests for the main module.
"""

import importlib.util
import pytest
import configparser
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.main import (
    load_config,
    parse_event_types,
    parse_proxy,
    create_event_forwarder,
    parse_args,
)


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_valid_config(self, temp_config_file):
        """Test loading a valid configuration file."""
        config = load_config(temp_config_file)
        
        assert isinstance(config, configparser.ConfigParser)
        assert config.get('lookout', 'entity_name') == 'test-company'
        assert config.get('lookout', 'api_domain') == 'https://api.lookout.com'
        assert config.get('syslog', 'host') == 'localhost'
        assert config.getint('syslog', 'port') == 514
    
    def test_load_missing_file(self):
        """Test loading a non-existent configuration file."""
        with pytest.raises(FileNotFoundError):
            load_config('/nonexistent/path/config.ini')
    
    def test_load_missing_required_section(self, temp_config_file):
        """Test loading config with missing required section."""
        # Create a config with missing syslog section
        with open(temp_config_file, 'w') as f:
            f.write("""
[lookout]
entity_name = test-company
api_domain = https://api.lookout.com
api_key = test-key
""")
        
        with pytest.raises(ValueError, match='Missing required section'):
            load_config(temp_config_file)


class TestParseEventTypes:
    """Tests for parse_event_types function."""
    
    def test_all_events_enabled(self, temp_config_file):
        """Test parsing when all event types are enabled."""
        config = load_config(temp_config_file)
        event_types = parse_event_types(config)
        
        assert 'THREAT' in event_types
        assert 'DEVICE' in event_types
        assert 'AUDIT' not in event_types
    
    def test_only_threat_enabled(self, temp_config_file):
        """Test parsing when only threat events are enabled."""
        with open(temp_config_file, 'w') as f:
            f.write("""
[lookout]
entity_name = test
device_enabled = false
threat_enabled = true
audit_enabled = false

[syslog]
host = localhost
port = 514
""")
        
        config = load_config(temp_config_file)
        event_types = parse_event_types(config)
        
        assert event_types == 'THREAT'
    
    def test_no_events_enabled_uses_default(self, temp_config_file):
        """Test that default events are used when none enabled."""
        with open(temp_config_file, 'w') as f:
            f.write("""
[lookout]
entity_name = test
device_enabled = false
threat_enabled = false
audit_enabled = false

[syslog]
host = localhost
port = 514
""")
        
        config = load_config(temp_config_file)
        event_types = parse_event_types(config)
        
        # Should default to THREAT,DEVICE
        assert 'THREAT' in event_types
        assert 'DEVICE' in event_types


class TestParseProxy:
    """Tests for parse_proxy function."""
    
    def test_no_proxy_configured(self, temp_config_file):
        """Test parsing when no proxy is configured."""
        config = load_config(temp_config_file)
        proxy = parse_proxy(config)
        
        assert proxy == {}
    
    @pytest.mark.skipif(
        importlib.util.find_spec("furl") is None,
        reason="furl module not installed"
    )
    def test_proxy_without_auth(self, temp_config_file):
        """Test parsing proxy without authentication."""
        with open(temp_config_file, 'w') as f:
            f.write("""
[lookout]
entity_name = test

[syslog]
host = localhost
port = 514

[proxy]
address = http://proxy.company.com:8080
username = 
password = 
""")
        
        config = load_config(temp_config_file)
        proxy = parse_proxy(config)
        
        assert 'http' in proxy
        assert 'proxy.company.com:8080' in proxy['http']


class TestCreateEventForwarder:
    """Tests for create_event_forwarder function."""

    def test_create_qradar_forwarder(self, temp_config_file):
        """QRadar forwarder is returned when forwarder_type=qradar."""
        config = load_config(temp_config_file)
        mock_logger = Mock()

        with patch("lookout_mra_client.event_forwarders.qradar_event_forwarder.SyslogClient"):
            forwarder = create_event_forwarder(config, mock_logger)

        assert forwarder.__class__.__name__ == "QRadarEventForwarder"
        mock_logger.info.assert_called_once()

    def test_create_splunk_forwarder(self, temp_config_file):
        """Splunk forwarder is returned when forwarder_type=splunk."""
        with open(temp_config_file, "w") as f:
            f.write("""
[lookout]
entity_name = test

[syslog]
host = localhost
port = 514
forwarder_type = splunk
""")
        config = load_config(temp_config_file)
        mock_logger = Mock()

        with patch("lookout_mra_client.event_forwarders.splunk_event_forwarder.SyslogClient"):
            forwarder = create_event_forwarder(config, mock_logger)

        assert forwarder.__class__.__name__ == "SplunkEventForwarder"

    def test_splunk_forwarder_receives_correct_address(self, temp_config_file):
        """create_event_forwarder must pass host:port to the Splunk forwarder."""
        with open(temp_config_file, "w") as f:
            f.write("""
[lookout]
entity_name = test

[syslog]
host = syslog.corp.internal
port = 5514
forwarder_type = splunk
use_udp = false
""")
        config = load_config(temp_config_file)
        mock_logger = Mock()

        with patch("lookout_mra_client.event_forwarders.splunk_event_forwarder.SyslogClient") as sc:
            sc.return_value = Mock()
            forwarder = create_event_forwarder(config, mock_logger)

        assert forwarder.syslog_address == ("syslog.corp.internal", 5514)

    def test_splunk_forwarder_udp_flag_propagated(self, temp_config_file):
        """use_udp=true in config selects SOCK_DGRAM for the Splunk forwarder."""
        import socket
        with open(temp_config_file, "w") as f:
            f.write("""
[lookout]
entity_name = test

[syslog]
host = localhost
port = 514
forwarder_type = splunk
use_udp = true
""")
        config = load_config(temp_config_file)
        mock_logger = Mock()

        with patch("lookout_mra_client.event_forwarders.splunk_event_forwarder.SyslogClient"):
            forwarder = create_event_forwarder(config, mock_logger)

        assert forwarder.socktype == socket.SOCK_DGRAM

    def test_qradar_forwarder_tcp_by_default(self, temp_config_file):
        """QRadar forwarder defaults to TCP when use_udp is absent."""
        import socket
        config = load_config(temp_config_file)
        mock_logger = Mock()

        with patch("lookout_mra_client.event_forwarders.qradar_event_forwarder.SyslogClient"):
            forwarder = create_event_forwarder(config, mock_logger)

        assert forwarder.socktype == socket.SOCK_STREAM


class TestParseArgs:
    """Tests for parse_args function."""
    
    def test_parse_required_config(self):
        """Test parsing required config argument."""
        test_args = ['--config', '/path/to/config.ini']
        
        with patch.object(sys, 'argv', ['mrav2-connector'] + test_args):
            args = parse_args()
            assert args.config == '/path/to/config.ini'
    
    def test_parse_optional_log_file(self):
        """Test parsing optional log file argument."""
        test_args = ['--config', 'config.ini', '--log-file', '/var/log/test.log']
        
        with patch.object(sys, 'argv', ['mrav2-connector'] + test_args):
            args = parse_args()
            assert args.log_file == '/var/log/test.log'
    
    def test_parse_verbose_flag(self):
        """Test parsing verbose flag."""
        test_args = ['--config', 'config.ini', '--verbose']
        
        with patch.object(sys, 'argv', ['mrav2-connector'] + test_args):
            args = parse_args()
            assert args.verbose is True
