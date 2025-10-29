import logging, threading, json, sys
from .event_forwarders.event_forwarder import EventForwarder
from .lookout_logger import LOGGER_NAME
from .mra_v2_stream import MRAv2Stream


class MRAv2StreamThread(threading.Thread):
    """
    Thread wrapper around MRAv2Stream. This allows a controlling program
    to control multiple mra v2 streams.
    """

    def __init__(self, entName: str, eventForwarder: EventForwarder, **kwargs) -> None:
        # The shutdown_flag is a threading.Event object that
        # indicates whether the thread should be terminated.
        self.shutdown_flag = threading.Event()
        self.shutdown_flag.clear()

        self.ent_name = entName
        self.event_forwarder = eventForwarder
        self.logger = logging.getLogger(LOGGER_NAME)
        self.error = None

        self.stream = MRAv2Stream(**kwargs)

        threading.Thread.__init__(self)

    def run(self) -> None:
        """
        Start listening for and writing events.
        """
        try:
            self.logger.info(
                f"{self.name} - Fetching {self.stream.event_type} events starting at id: {self.stream.last_event_id} or time: {self.stream.start_time}"
            )
            for event in self.stream.listenForEvents():
                if self.shutdown_flag.is_set():
                    self.stream.shutdown()
                    sys.exit(0)

                if event.event == "events":
                    mra_events = []
                    try:
                        mra_events = json.loads(event.data).get("events", [])
                    except Exception as e:
                        self.logger.error(f"failed to parse mra events from sse client: {e}")

                    self.logger.debug(f"{self.name} - received {len(mra_events)} event(s)")
                    self.event_forwarder.write_all(mra_events, self.ent_name)
                elif event.event == "heartbeat":
                    self.logger.debug(f"{self.name} - received heartbeat")
            self.stream.shutdown()
        except Exception as e:
            self.logger.error(f"{self.name} - Exception in stream thread: {str(e)}")
            self.error = sys.exc_info()
