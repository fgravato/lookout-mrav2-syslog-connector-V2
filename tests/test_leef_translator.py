"""
Tests for the LEEF translator module.
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.event_translators.leef_translator import LeefTranslator


class TestLeefTranslator:
    """Tests for LeefTranslator class."""
    
    @pytest.fixture
    def translator(self):
        """Create a LEEF translator instance."""
        return LeefTranslator(mra_v2=True)
    
    def test_format_threat_event(self, translator, sample_mra_v2_threat_event):
        """Test formatting a threat event."""
        result = translator.formatEvent(sample_mra_v2_threat_event)
        
        # Check LEEF header format
        assert 'LEEF:2.0' in result
        assert 'Lookout' in result
        assert 'MRAv2 Client' in result
        assert 'THREAT' in result
        assert 'malware' in result  # Classification should be in category
        
    def test_format_device_event(self, translator, sample_mra_v2_device_event):
        """Test formatting a device event."""
        result = translator.formatEvent(sample_mra_v2_device_event)
        
        assert 'LEEF:2.0' in result
        assert 'DEVICE' in result
        assert 'ACTIVATED' in result
    
    def test_format_audit_event(self, translator, sample_mra_v2_audit_event):
        """Test formatting an audit event."""
        result = translator.formatEvent(sample_mra_v2_audit_event)
        
        assert 'LEEF:2.0' in result
        assert 'AUDIT' in result
        assert 'user_login' in result
    
    def test_missing_qradar_log_source_identifier(self, translator):
        """Test handling missing qradarLogSourceIdentifier field."""
        event = {
            "type": "THREAT",
            "change_type": "test",
            "threat": {
                "classifications": ["malware"]
            },
            "details": {"type": "THREAT"}
            # Note: qradarLogSourceIdentifier is missing
        }
        
        # Should not raise KeyError
        result = translator.formatEvent(event)
        assert 'LOOKOUT' in result  # Default value used
    
    def test_missing_type_field(self, translator):
        """Test handling missing type field."""
        event = {
            "change_type": "test",
            "qradarLogSourceIdentifier": "TEST",
            "details": {"type": "UNKNOWN"}
            # Note: type is missing
        }
        
        # Should not raise KeyError
        result = translator.formatEvent(event)
        assert 'UNKNOWN' in result  # Default value used
    
    def test_device_deleted_status(self, translator):
        """Test formatting device with DELETED status."""
        event = {
            "type": "DEVICE",
            "change_type": "device_deleted",
            "qradarLogSourceIdentifier": "TEST",
            "device": {
                "status": {
                    "activation_status": "DELETED"
                }
            },
            "details": {"type": "DEVICE"}
        }
        
        result = translator.formatEvent(event)
        assert 'DELETED' in result
    
    def test_leef_field_separator(self, translator, sample_mra_v2_threat_event):
        """Test that LEEF uses tab separator for attributes."""
        result = translator.formatEvent(sample_mra_v2_threat_event)
        
        # Check that tab separator is used
        assert '\t' in result
