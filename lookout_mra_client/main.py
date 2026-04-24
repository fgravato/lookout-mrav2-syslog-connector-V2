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
import time
from datetime import datetime

from .lookout_logger import init_lookout_logger
from .mra_v2_stream_thread import MRAv2StreamThread
from .stream_position_file import StreamPositionFile
from .event_forwarders.qradar_event_forwarder import QRadarEventForwarder
from .event_forwarders.splunk_event_forwarder import SplunkEventForwarder
from .event_forwarders.event_forwarder import EventForwarder

shutdown_event = threading.Event()

# Type alias for config
ConfigType = configparser.ConfigParser


_SAVE_INTERVAL_SECONDS = 30  # how often to persist stream_position during normal operation


def _warn_if_config_world_readable(config_file: str, logger: logging.Logger) -> None:
    """Warn if the config file is readable by users other than the owner."""
    try:
        mode = os.stat(config_file).st_mode
        if mode & 0o044:  # group-readable or world-readable
            logger.warning(
                f"Config file {config_file} may be readable by other users. "
                f"It contains API credentials — tighten permissions: chmod 600 {config_file}"
            )
    except OSError:
        pass


def default_state_file(config_file: str) -> str:
    """Derive the default state file path from the config file path.

    Example: /etc/mrav2/config.ini -> /etc/mrav2/config.state
    """
    base = os.path.splitext(os.path.abspath(config_file))[0]
    return base + ".state"


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
        "-s",
        "--state-file",
        default=None,
        help="Path to stream position state file (default: <config>.state)",
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


def load_config(config_file: str) -> configparser.ConfigParser:
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


def parse_event_types(config: ConfigType) -> str:
    """Parse enabled event types from config"""
    event_types = []

    if config.getboolean("lookout", "threat_enabled", fallback=True):
        event_types.append("THREAT")
    if config.getboolean("lookout", "device_enabled", fallback=True):
        event_types.append("DEVICE")
    if config.getboolean("lookout", "audit_enabled", fallback=False):
        event_types.append("AUDIT")

    return ",".join(event_types) if event_types else "THREAT,DEVICE"


def parse_proxy(config: ConfigType) -> dict:
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
    config: ConfigType, logger: logging.Logger
) -> EventForwarder:
    """Create appropriate event forwarder based on config"""
    syslog_host = config.get("syslog", "host", fallback="localhost")
    syslog_port = config.getint("syslog", "port", fallback=514)
    if not 1 <= syslog_port <= 65535:
        raise ValueError(f"syslog port must be 1–65535, got {syslog_port}")
    forwarder_type = config.get("syslog", "forwarder_type", fallback="qradar").lower()

    log_identifier_key = config.get("syslog", "log_identifier_key", fallback="")
    log_identifier = config.get("syslog", "log_identifier", fallback="")
    use_udp = config.getboolean("syslog", "use_udp", fallback=False)

    console_address = (syslog_host, syslog_port)

    if forwarder_type == "splunk":
        protocol = "UDP" if use_udp else "TCP"
        logger.info(f"Using Splunk event forwarder to {syslog_host}:{syslog_port} ({protocol})")
        return SplunkEventForwarder(
            syslog_address=console_address,
            callback=None,
            use_udp=use_udp,
        )
    else:
        protocol = "UDP" if use_udp else "TCP"
        logger.info(f"Using QRadar event forwarder to {syslog_host}:{syslog_port} ({protocol})")
        return QRadarEventForwarder(
            console_address, log_identifier_key, log_identifier, None, use_udp=use_udp
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
        _warn_if_config_world_readable(args.config, logger)

        entity_name = config.get("lookout", "entity_name")
        api_domain = config.get("lookout", "api_domain")
        api_key = config.get("lookout", "api_key")
        event_types = parse_event_types(config)
        proxies = parse_proxy(config)
        start_time_str = config.get("lookout", "start_time", fallback="")
        sse_timeout = config.getint("lookout", "sse_timeout", fallback=10)

        logger.info(f"Entity: {entity_name}")
        logger.info(f"API Domain: {api_domain}")
        logger.info(f"Event Types: {event_types}")

        # Resolve stream position state file
        state_file_path = args.state_file or default_state_file(args.config)
        pos_file = StreamPositionFile(state_file_path)
        logger.info(f"Stream position state file: {state_file_path}")

        # Create event forwarder
        event_forwarder = create_event_forwarder(config, logger)

        # Setup stream arguments
        stream_args = {
            "api_domain": api_domain,
            "api_key": api_key,
            "event_type": event_types,
            "proxies": proxies,
            "timeout": sse_timeout,
        }

        # Resolve starting position.
        #
        # Priority:
        #   1. State file  — written at runtime; survives restarts without touching config.ini
        #   2. config.ini stream_position  — one-time migration for existing deployments
        #   3. config.ini start_time  — ISO timestamp configured by the operator
        #   4. Built-in default  — replay all available history (2020-01-01)
        #
        # NOTE: The Lookout API treats id=0 as "start from current position"
        # (live tail).  A start_time is required to replay historical events.
        stream_position = pos_file.read()
        if stream_position:
            stream_args["last_event_id"] = stream_position
            logger.info(f"Resuming from stream position: {stream_position} (state file)")
        else:
            # Migration: honour a position written to config.ini by an older version
            legacy_position = config.get("lookout", "stream_position", fallback="0")
            if legacy_position and legacy_position != "0":
                stream_args["last_event_id"] = legacy_position
                logger.info(
                    f"Resuming from stream position: {legacy_position} (migrated from config.ini)"
                )
                # Persist to the state file so future restarts don't touch config.ini
                pos_file.write(legacy_position, entity_name)
            elif start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
                stream_args["start_time"] = start_time
                logger.info(f"Starting from time: {start_time}")
            else:
                default_start = datetime(2020, 1, 1)
                stream_args["start_time"] = default_start
                logger.warning(
                    f"No position or start_time configured — replaying ALL history "
                    f"from {default_start.date()}. Set start_time in config to limit replay."
                )

        # Create and start MRA stream thread
        mra_thread = MRAv2StreamThread(entity_name, event_forwarder, **stream_args)
        mra_thread.start()

        logger.info("MRAv2 Syslog Connector started successfully")
        logger.info("Press Ctrl+C to stop")

        # Wait for shutdown signal, periodically persisting the stream position
        # so that a clean restart resumes from where we left off.
        last_saved_position = ""
        last_save_time = time.time()
        while not shutdown_event.is_set():
            threading.Event().wait(1)
            now = time.time()
            if now - last_save_time >= _SAVE_INTERVAL_SECONDS:
                current_position = mra_thread.stream.last_event_id
                if current_position and current_position != last_saved_position:
                    pos_file.write(current_position, entity_name)
                    logger.debug(f"Stream position {current_position} saved")
                    last_saved_position = current_position
                last_save_time = now

        # Shutdown gracefully
        logger.info("Shutting down...")
        mra_thread.shutdown_flag.set()
        if mra_thread.is_alive():
            mra_thread.join(timeout=10)

        # Final save so the next restart resumes exactly where we stopped
        final_position = mra_thread.stream.last_event_id
        if final_position and final_position != last_saved_position:
            pos_file.write(final_position, entity_name)
            logger.info(f"Stream position {final_position} saved on shutdown")

        logger.info("MRAv2 Syslog Connector stopped")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
