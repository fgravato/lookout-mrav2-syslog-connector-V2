import time

from typing import Tuple
from datetime import datetime
from types import ModuleType

from ..models.configuration import Configuration, format_proxy, event_type_display
from ..lookout_logger import init_lookout_logger
from ..event_forwarders.qradar_event_forwarder import QRadarEventForwarder
from ..mra_v2_stream_thread import MRAv2StreamThread


MAX_BACKOFF_SEC = 600
BACKOFF_INTERVAL_SEC = 15


class MRAEventRunnerV2:
    """
    MRA Event Runner V2

    Background service that looks for a mra configuration in the database,
    pulls events from the MRA v2 SSE stream and outputs them to syslog.

    Used for DB-based deployments (not the standalone config.ini flow).
    """

    def __init__(
        self,
        console_address: Tuple[str, int],
        config_load_sleep: int,
        config_check_sleep: int,
        secrets_manager: ModuleType,
        log_file: str,
        log_identifier_key: str = "",
        log_identifier: str = "",
    ) -> None:
        self.config_load_sleep = config_load_sleep
        self.config_check_sleep = config_check_sleep
        self.secrets_manager = secrets_manager
        self.log_file = log_file
        self.running = True

        self.event_forwarder = QRadarEventForwarder(
            console_address, log_identifier_key, log_identifier, self.__save_config
        )
        self.configuration: Configuration = None
        self.mra_v2 = None

    def __save_config(self, events: list):
        if len(events) > 0:
            self.logger.info(f"Wrote {len(events)} events to syslog")

            if self.mra_v2.stream.last_event_id != self.configuration.stream_position:
                self.configuration.stream_position = self.mra_v2.stream.last_event_id
                self.configuration.fetch_count += len(events)
        else:
            self.logger.info("No new events...")

        self.configuration.fetched_at = datetime.now()
        self.configuration.save(
            only=[
                Configuration.stream_position,
                Configuration.fetch_count,
                Configuration.fetched_at,
            ]
        )

    def __restart_mra(self):
        if self.mra_v2:
            self.mra_v2.shutdown_flag.set()
            self.mra_v2.join()

        stream_args = {
            "api_domain": self.configuration.api_domain,
            "api_key": self.configuration.api_key,
            "event_type": event_type_display(self.configuration),
            "proxies": format_proxy(self.configuration),
        }

        stream_position = self.configuration.stream_position
        if stream_position:
            stream_args["last_event_id"] = stream_position
        else:
            stream_args["start_time"] = self.configuration.start_time

        self.mra_v2 = MRAv2StreamThread(
            self.configuration.ent_name, self.event_forwarder, **stream_args
        )
        self.mra_v2.start()

    def __configure(self):
        current_config = self.configuration
        while True:
            self.logger.info("Attempting to retrieve configuration from db...")
            self.configuration = Configuration.get_configuration_by_id(
                1, load_secrets=True, secrets_manager=self.secrets_manager
            )

            if self.configuration is not None:
                self.logger.info("Configuration found")
                if not current_config or self.configuration != current_config:
                    self.logger.info("Setting up new event thread")
                    self.__restart_mra()
                break
            else:
                self.logger.info("Sleeping until configuration is available")
                time.sleep(self.config_load_sleep)

    def start(self):
        self.logger = init_lookout_logger(self.log_file)
        self.__configure()

        while self.running:
            time.sleep(self.config_check_sleep)
            self.__configure()

        self.mra_v2.shutdown_flag.set()
        if self.mra_v2.is_alive():
            self.mra_v2.join()
