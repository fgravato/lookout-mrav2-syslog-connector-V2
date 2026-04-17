import json
import socket
import time

from .event_forwarder import EventForwarder
from ..syslog_client import SyslogClient

# Reconnect the syslog socket after this many idle seconds (matches QRadar threshold).
_RECONNECT_IDLE_SECONDS = 600


class SplunkEventForwarder(EventForwarder):
    """
    Forwards MRAv2 events as JSON-formatted syslog messages over TCP (or UDP)
    to a Splunk Universal Forwarder or any syslog receiver configured for
    Splunk ingestion.

    Uses the same SyslogClient transport as QRadarEventForwarder, but sends
    a raw JSON payload instead of a LEEF-formatted string.
    """

    def __init__(self, syslog_address: tuple, callback=None, use_udp: bool = False):
        self.syslog_address = syslog_address
        self.callback = callback
        self.socktype = socket.SOCK_DGRAM if use_udp else socket.SOCK_STREAM
        self._syslog_client = self._create_client()
        self._last_write_time = None

    def _create_client(self) -> SyslogClient:
        return SyslogClient(
            "MRAv2SplunkSyslogClient",
            json.dumps,
            self.syslog_address,
            socktype=self.socktype,
            log_internally=False,
        )

    def _reconnect(self) -> None:
        """Close the existing client and open a fresh connection."""
        try:
            self._syslog_client.close()
        except Exception:
            pass
        self._syslog_client = self._create_client()

    def write_all(self, events: list, entName: str = "") -> None:
        now = time.time()
        if self._last_write_time is not None and (now - self._last_write_time) > _RECONNECT_IDLE_SECONDS:
            self._reconnect()
        super().write_all(events, entName)
        self._last_write_time = time.time()
        if self.callback:
            self.callback(events)

    def write(self, event: dict, entName: str = "") -> None:
        """
        Annotate and forward one MRAv2 event as a JSON syslog message.

        Args:
            event (dict): MRAv2 event dict.
            entName (str): Enterprise name injected into the payload.
        """
        event["entName"] = entName
        event["type"] = event.get("type", "UNKNOWN")
        self._syslog_client.write(event)
