import json, sys
from .event_forwarder import EventForwarder

# Splunk requires a `\r\n` at the end of each event emitted.
SPLUNK_EVENT_DELIMITER = "\r\n"


class SplunkEventForwarder(EventForwarder):
    """
    Splunk indexes the STDOUT of a data input script
    """

    def __init__(self, callback=None):
        self.callback = callback

    def write_all(self, events, entName=""):
        super().write_all(events, entName)
        if self.callback:
            self.callback(events)

    def write(self, event: dict, entName: str = "") -> None:
        """
        Write a MRA v2 event to Splunk

        Args:
            event (dict): MRA v2 event
            entName (str): Enterprise name.
        """
        event["entName"] = entName
        event["type"] = event.get("type", "UNKNOWN")
        sys.stdout.write(json.dumps(event) + SPLUNK_EVENT_DELIMITER)
