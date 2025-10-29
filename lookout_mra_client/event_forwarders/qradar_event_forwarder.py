import time

from .event_forwarder import EventForwarder
from ..event_translators.leef_translator import LeefTranslator
from ..syslog_client import SyslogClient


class QRadarEventForwarder(EventForwarder):
    """
    Lookout's QRadar plugin utilizes a syslog connection to forward events for ingestion.
    """

    def __init__(self, qradar_address, log_identifier_key, log_identifier, callback):
        self.qradar_address = qradar_address
        self.event_translator = LeefTranslator(mra_v2=True)
        self.log_identifier_key = log_identifier_key
        self.log_identifier = log_identifier
        self.callback = callback

    def write_all(self, events: list, entName: str):
        """
        Write a MRA v2 event to QRadar

        Args:
            event (dict): MRA v2 event

        Initialize Syslog Client here to avoid the syslog socket getting stale
        JIRA: EMM-8312: Events stop appearing in QRadar if there has been long (~15 minute)
        break between events
        """
        client_name = "MRAv2SyslogClient" + str(time.time())
        syslog_client = SyslogClient(
            client_name, self.event_translator.formatEvent, self.qradar_address
        )

        for event in events:
            # set defaults if not present
            event["entName"] = entName
            event["details"] = event.get("details", {})
            event["details"]["type"] = event["details"].get("type", "UNKNOWN")
            if self.log_identifier_key:
                event[self.log_identifier_key] = self.log_identifier

            # Write to syslog
            syslog_client.write(event)

        self.callback(events)
