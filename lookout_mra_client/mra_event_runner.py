from typing import Tuple

import time
from datetime import datetime
from random import randrange
from types import ModuleType

from .models.configuration import Configuration, format_proxy, event_type_display
from .lookout_logger import init_lookout_logger
from .mra_client import MRAClient
from .syslog_client import SyslogClient

MAX_BACKOFF_SEC = 600
BACKOFF_INTERVAL_SEC = 15


class MRAEventRunner:
    """
    MRA Event Runner

    Background service that looks for a mra configuration, pulls
    events from the MRA and outputs them to syslog.
    """

    def __init__(
        self,
        console_address: Tuple[str, int],
        config_load_sleep: int,
        config_refresh_interval: int,
        events_fetch_sleep: int,
        events_per_fetch: int,
        max_error_count: int,
        secrets_manager: ModuleType,
        event_formatter: callable,
        log_file: str,
        log_identifier_key: str = "",
        log_identifier: str = "",
        user_agent: str = "MRAEventRunner",
    ) -> None:
        self.console_address = console_address
        self.config_load_sleep = config_load_sleep
        self.config_refresh_interval = config_refresh_interval
        self.events_fetch_sleep = events_fetch_sleep
        self.events_per_fetch = events_per_fetch
        self.max_error_count = max_error_count
        self.secrets_manager = secrets_manager
        self.user_agent = user_agent

        self.event_formatter = event_formatter

        self.log_file = log_file
        self.log_identifier_key = log_identifier_key
        self.log_identifier = log_identifier

        self.configuration = None
        self.error_count = 0
        self.refresh_config_count = 0

        self.mra_client = None

        self.running = True

    def __configure(self) -> None:
        """
        Waits for a configuration to be present in the database, sets up the various components
        required for fetching and emitting events.
        """
        while True:
            self.logger.info("Attempting to retrieve configuration from db...")
            self.configuration = Configuration.get_configuration_by_id(
                1, load_secrets=True, secrets_manager=self.secrets_manager
            )

            if self.configuration is not None:
                self.logger.info("Configuration found, setting up event runner...")
                break
            else:
                self.logger.info("Sleeping until configuration is available")
                time.sleep(self.config_load_sleep)

        stream_position = -1
        if self.configuration.stream_position and self.configuration.stream_position.isdigit():
            stream_position = int(self.configuration.stream_position)
        self.mra_client = MRAClient(
            self.configuration.api_domain,
            self.configuration.api_key,
            stream_position,
            self.configuration.start_time,
            event_type_display(self.configuration),
            format_proxy(self.configuration),
            user_agent=self.user_agent,
        )

    def __fetch_events(self) -> None:
        """
        Inner loop function for fetching events from the MRA
        """
        events = self.mra_client.get_events(limit=self.events_per_fetch)

        if len(events) > 0:
            self.logger.info("Received {} events from mra".format(len(events)))

            """
            Initialize Syslog Client here to avoid the syslog socket getting stale
            JIRA: EMM-8312: Events stop appearing in QRadar if there has been long (~15 minute)
            break between events
            """
            client_name = "SyslogClient" + str(time.time())
            syslog_client = SyslogClient(client_name, self.event_formatter, self.console_address)

            for event in events:
                # set defaults if not present
                event["entName"] = self.configuration.ent_name
                event["details"]["type"] = event["details"].get("type", "UNKNOWN")
                if self.log_identifier_key:
                    event[self.log_identifier_key] = self.log_identifier

                # Write to syslog
                syslog_client.write(event)

            self.logger.info("Wrote {} events to syslog".format(len(events)))

            # Save current stream position to avoid repeating events.
            saved_position = -1
            if self.configuration.stream_position and self.configuration.stream_position.isdigit():
                saved_position = int(self.configuration.stream_position)
            if int(self.mra_client.stream_position) > saved_position:
                self.configuration.stream_position = str(self.mra_client.stream_position)
                self.configuration.fetch_count += len(events)
        else:
            self.logger.info("No new events...")

        self.configuration.fetched_at = datetime.now()
        # Only update the event runner specific fields to avoid stepping on new configuration updates from the UI
        self.configuration.save(
            only=[
                Configuration.stream_position,
                Configuration.fetch_count,
                Configuration.fetched_at,
            ]
        )

    def run_loop(self) -> int:
        """
        Run an infinite loop of fetching events from MRA and emitting them to syslog
        """
        self.error_count = 0
        self.refresh_config_count = 0

        self.logger = init_lookout_logger(self.log_file)

        self.__configure()

        while self.running:
            try:
                if self.refresh_config_count == self.config_refresh_interval:
                    self.refresh_config_count = 0
                    self.logger.info("Refreshing configuration from db")
                    self.__configure()

                self.__fetch_events()

                self.error_count = 0
                self.refresh_config_count += 1

                time.sleep(self.events_fetch_sleep)
            except Exception:
                self.logger.exception("Error fetching events")
                self.error_count += 1
                # Force reload configuration on next attempt
                self.refresh_config_count = self.config_refresh_interval

                # NOTE: Custom return code used by supervisord for automatic restart
                if self.error_count >= self.max_error_count:
                    self.logger.error("Maximum attempts reached, goodbye.")
                    return 2

                # backoff on each following error
                # (self.error_count + 1) bc randrange can not be called on the same number twice
                backoff = min(
                    MAX_BACKOFF_SEC,
                    randrange(
                        BACKOFF_INTERVAL_SEC, BACKOFF_INTERVAL_SEC * (self.error_count + 1) ** 2
                    ),
                )
                self.logger.error("Backing off '{}' seconds before retrying.".format(backoff))
                time.sleep(backoff)
