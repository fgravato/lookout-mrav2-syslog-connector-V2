import socket
import time

from .event_forwarder import EventForwarder
from ..event_translators.leef_translator import LeefTranslator
from ..syslog_client import SyslogClient

# Reconnect the syslog socket after this many idle seconds.
# Chosen to be safely under the ~15-minute staleness window from EMM-8312.
_RECONNECT_IDLE_SECONDS = 600


class QRadarEventForwarder(EventForwarder):
    """
    Lookout's QRadar plugin utilizes a syslog connection to forward events for ingestion.
    """

    def __init__(self, qradar_address, log_identifier_key, log_identifier, callback, use_udp=False):
        self.qradar_address = qradar_address
        self.event_translator = LeefTranslator(mra_v2=True)
        self.log_identifier_key = log_identifier_key
        self.log_identifier = log_identifier
        self.callback = callback
        self.socktype = socket.SOCK_DGRAM if use_udp else socket.SOCK_STREAM
        self._syslog_client = self._create_client()
        self._last_write_time = None

    def _create_client(self) -> SyslogClient:
        return SyslogClient(
            "MRAv2QRadarSyslogClient",
            self.event_translator.formatEvent,
            self.qradar_address,
            socktype=self.socktype,
            log_internally=True,
        )

    def _reconnect(self) -> None:
        """Close the existing client and open a fresh connection."""
        try:
            self._syslog_client.close()
        except OSError:
            pass
        self._syslog_client = self._create_client()

    def write_all(self, events: list, ent_name: str):
        """
        Write a MRA v2 event to QRadar

        Args:
            events (list): MRA v2 events
            entName (str): Enterprise name.

        The syslog client is reused across batches for efficiency.  If no
        events have been sent for longer than _RECONNECT_IDLE_SECONDS, the
        socket is recycled before sending so that stale TCP connections do not
        silently drop events (EMM-8312: events stop appearing in QRadar after
        ~15-minute gaps between events).
        """
        now = time.time()
        if self._last_write_time is not None and (now - self._last_write_time) > _RECONNECT_IDLE_SECONDS:
            self._reconnect()

        def flatten_events():
            """Flatten SMISHING_ALERT events with multiple detections into individual events."""
            for event in events:
                if event.get("type") == "SMISHING_ALERT":
                    smishing = event.get("smishing_alert", {})
                    detections = smishing.get("detections", [])
                    if detections:
                        for detection in detections:
                            # Targeted copy: only allocate two new dicts instead of
                            # recursively deep-copying the entire event.  We copy
                            # smishing_alert without the detections list and inject
                            # the single detection, then build a new top-level dict.
                            new_smishing = {k: v for k, v in smishing.items() if k != "detections"}
                            new_smishing["detection"] = detection
                            yield {**event, "smishing_alert": new_smishing}
                    else:
                        yield event
                else:
                    yield event

        flattened_events = list(flatten_events())

        for event in flattened_events:
            # set defaults if not present
            event["entName"] = ent_name
            event["details"] = event.get("details", {})
            event["details"]["type"] = event["details"].get("type", "UNKNOWN")
            if self.log_identifier_key:
                event[self.log_identifier_key] = self.log_identifier

            # Write to syslog
            self._syslog_client.write(event)

        self._last_write_time = time.time()

        if self.callback:
            self.callback(flattened_events)
