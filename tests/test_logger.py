"""
Tests for the logger module.
"""

import pytest
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lookout_mra_client.lookout_logger import init_lookout_logger, LOGGER_NAME


@pytest.fixture(autouse=True)
def clear_logger():
    """Clear the logger handlers before each test."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers = []
    yield
    # Cleanup after test
    logger.handlers = []


class TestInitLookoutLogger:
    """Tests for init_lookout_logger function."""
    
    def test_logger_creation(self, temp_log_file):
        """Test that logger is created with correct settings."""
        logger = init_lookout_logger(temp_log_file)
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == LOGGER_NAME
        assert logger.level == logging.DEBUG
        assert logger.propagate is False
    
    def test_logger_handlers_added(self, temp_log_file):
        """Test that file handler is added to logger."""
        logger = init_lookout_logger(temp_log_file)
        
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)
    
    def test_logger_handlers_not_duplicated(self, temp_log_file):
        """Test that calling init twice doesn't duplicate handlers."""
        logger1 = init_lookout_logger(temp_log_file)
        logger2 = init_lookout_logger(temp_log_file)
        
        # Should be the same logger instance
        assert logger1 is logger2
        # Should still only have one handler
        assert len(logger1.handlers) == 1
    
    def test_log_file_created(self, temp_log_file):
        """Test that log file is created."""
        logger = init_lookout_logger(temp_log_file)
        logger.info("Test message")
        
        # Flush the handler to ensure data is written
        for handler in logger.handlers:
            handler.flush()
        
        assert os.path.exists(temp_log_file)
        
        with open(temp_log_file, 'r') as f:
            content = f.read()
            assert "Test message" in content
    
    def test_log_format(self, temp_log_file):
        """Test that log format is correct."""
        logger = init_lookout_logger(temp_log_file)
        logger.info("Test message")
        
        # Flush the handler to ensure data is written
        for handler in logger.handlers:
            handler.flush()
        
        with open(temp_log_file, 'r') as f:
            content = f.read()
            # Check format contains expected components
            assert LOGGER_NAME in content
            assert "INFO" in content
            assert "Test message" in content
    
    def test_rotating_file_handler_settings(self, temp_log_file):
        """Test that rotating file handler has correct settings."""
        logger = init_lookout_logger(
            temp_log_file,
            maxMegabytes=20,
            backupCount=10
        )
        
        handler = logger.handlers[0]
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        # maxBytes should be 20 * 1,000,000 = 20,000,000
        assert handler.maxBytes == 20000000
        assert handler.backupCount == 10
    
    def test_custom_log_level(self, temp_log_file):
        """Test that custom log level is set correctly."""
        logger = init_lookout_logger(temp_log_file, level=logging.ERROR)
        
        assert logger.level == logging.ERROR
        
        # INFO messages should not be logged
        logger.info("This should not appear")
        
        # Flush the handler to ensure data is written
        for handler in logger.handlers:
            handler.flush()
        
        with open(temp_log_file, 'r') as f:
            content = f.read()
            assert "This should not appear" not in content
