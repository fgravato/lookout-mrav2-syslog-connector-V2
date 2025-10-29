#!/usr/bin/env python3
"""
MRAv2 Syslog Connector - Main Entry Point

Streams events from Lookout Mobile Risk API v2 and forwards them to syslog.
"""

import argparse
import configparser
import logging
import os
import signal
import sys
import threading
from datetime import datetime
from typing import Tuple

from .lookout_logger import init_lookout_logger
from .mra_v2_stream_thread import MRAv2StreamThread
from .event_forwarders.qradar_event_forwarder import QRadarEventForwarder
from .event_forwarders.splunk_event_forwarder import SplunkEventForwarder

shutdown_event = threading.Event()


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print("\nShutdown signal received. Stopping connector...")
    shutdown_event.set()
    sys.exit(0)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Lookout Mobile Risk API v2 to Syslog Connector"
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Path to configuration INI file",
    )
    parser.add_argument(
        "-l",
        "--log-file",
        default="/var/log/mrav2-syslog-connector.log",
        help="Path to log file (default: /var/log/mrav2-syslog-connector.log)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def load_config(config_file: str) -> dict:
    """Load configuration from INI file"""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    config = configparser.ConfigParser()
    config.read(config_file)

    required_sections = ["lookout", "syslog"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section in config: [{section}]")

    return config


def parse_event_types(config: configparser.ConfigParser) -> str:
    """Parse enabled event types from config"""
    event_types = []
    
    if config.getboolean("lookout", "threat_enabled", fallback=True):
        event_types.append("THREAT")
    if config.getboolean("lookout", "device_enabled", fallback=True):
        event_types.append("DEVICE")
    if config.getboolean("lookout", "audit_enabled", fallback=False):
        event_types.append("AUDIT")

    return ",".join(event_types) if event_types else "THREAT,DEVICE"


def parse_proxy(config: configparser.ConfigParser) -> dict:
    """Parse proxy configuration"""
    if "proxy" not in config:
        return {}

    proxy_addr = config.get("proxy", "address", fallback="")
    if not proxy_addr:
        return {}

    proxy_username = config.get("proxy", "username", fallback="")
    proxy_password = config.get("proxy", "password", fallback="")

    if proxy_username and proxy_password:
        # Format: scheme://username:password@host:port
        from furl import furl
        url = furl(proxy_addr)
        url.username = proxy_username
        url.password = proxy_password
        proxy_addr = url.tostr()

    # Return proxy dict for requests library
    from furl import furl
    url = furl(proxy_addr)
    if url.scheme:
        return {url.scheme: proxy_addr}
    return {}


def create_event_forwarder(
    config: configparser.ConfigParser, logger: logging.Logger
) -> Tuple:
    """Create appropriate event forwarder based on config"""
    syslog_host = config.get("syslog", "host", fallback="localhost")
    syslog_port = config.getint("syslog", "port", fallback=514)
    forwarder_type = config.get("syslog", "forwarder_type", fallback="qradar").lower()
    
    log_identifier_key = config.get("syslog", "log_identifier_key", fallback="")
    log_identifier = config.get("syslog", "log_identifier", fallback="")

    console_address = (syslog_host, syslog_port)

    if forwarder_type == "splunk":
        logger.info(f"Using Splunk event forwarder to {syslog_host}:{syslog_port}")
        return SplunkEventForwarder(
            console_address, log_identifier_key, log_identifier, None
        )
    else:
        logger.info(f"Using QRadar event forwarder to {syslog_host}:{syslog_port}")
        return QRadarEventForwarder(
            console_address, log_identifier_key, log_identifier, None
        )


def main():
    """Main entry point"""
    args = parse_args()

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize logger
    logger = init_lookout_logger(args.log_file)
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("MRAv2 Syslog Connector Starting")
    logger.info("=" * 60)

    try:
        # Load configuration
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")

        # Parse configuration
        entity_name = config.get("lookout", "entity_name")
        api_domain = config.get("lookout", "api_domain")
        api_key = config.get("lookout", "api_key")
        event_types = parse_event_types(config)
        proxies = parse_proxy(config)
        
        stream_position = config.get("lookout", "stream_position", fallback="0")
        start_time_str = config.get("lookout", "start_time", fallback="")

        logger.info(f"Entity: {entity_name}")
        logger.info(f"API Domain: {api_domain}")
        logger.info(f"Event Types: {event_types}")

        # Create event forwarder
        event_forwarder = create_event_forwarder(config, logger)

        # Setup stream arguments
        stream_args = {
            "api_domain": api_domain,
            "api_key": api_key,
            "event_type": event_types,
            "proxies": proxies,
        }

        # Set stream position or start time
        if stream_position and stream_position != "0":
            stream_args["last_event_id"] = int(stream_position)
            logger.info(f"Starting from stream position: {stream_position}")
        elif start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            stream_args["start_time"] = start_time
            logger.info(f"Starting from time: {start_time}")
        else:
            stream_args["last_event_id"] = 0
            logger.info("Starting from beginning (position 0)")

        # Create and start MRA stream thread
        mra_thread = MRAv2StreamThread(entity_name, event_forwarder, **stream_args)
        mra_thread.start()

        logger.info("MRAv2 Syslog Connector started successfully")
        logger.info("Press Ctrl+C to stop")

        # Wait for shutdown signal
        while not shutdown_event.is_set():
            threading.Event().wait(1)

        # Shutdown gracefully
        logger.info("Shutting down...")
        mra_thread.shutdown_flag.set()
        if mra_thread.is_alive():
            mra_thread.join(timeout=10)
        
        logger.info("MRAv2 Syslog Connector stopped")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
