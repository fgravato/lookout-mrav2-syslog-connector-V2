"""
Pytest configuration and shared fixtures for MRAv2 Syslog Connector tests.
"""

import pytest
import tempfile
import os


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config_content = """
[lookout]
entity_name = test-company
api_domain = https://api.lookout.com
api_key = test-api-key
threat_enabled = true
device_enabled = true
audit_enabled = false
stream_position = 0

[syslog]
host = localhost
port = 514
forwarder_type = qradar

[proxy]
address = 
username = 
password = 
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(config_content)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def sample_mra_v2_threat_event():
    """Sample MRA v2 threat event for testing."""
    return {
        "type": "THREAT",
        "change_type": "threat_detected",
        "entName": "test-company",
        "qradarLogSourceIdentifier": "LOOKOUT-123",
        "threat": {
            "classifications": ["malware", "trojan"]
        },
        "details": {
            "type": "THREAT"
        }
    }


@pytest.fixture
def sample_mra_v2_device_event():
    """Sample MRA v2 device event for testing."""
    return {
        "type": "DEVICE",
        "change_type": "device_updated",
        "entName": "test-company",
        "qradarLogSourceIdentifier": "LOOKOUT-123",
        "device": {
            "status": {
                "activation_status": "ACTIVATED",
                "security_status": "SECURE"
            }
        },
        "details": {
            "type": "DEVICE"
        }
    }


@pytest.fixture
def sample_mra_v2_audit_event():
    """Sample MRA v2 audit event for testing."""
    return {
        "type": "AUDIT",
        "change_type": "audit_log",
        "entName": "test-company",
        "qradarLogSourceIdentifier": "LOOKOUT-123",
        "audit": {
            "type": "user_login"
        },
        "details": {
            "type": "AUDIT"
        }
    }
