import json
import logging
import queue
import sys
import threading
from typing import Optional
from .event_forwarders.event_forwarder import EventForwarder
from .lookout_logger import LOGGER_NAME
from .mra_v2_stream import MRAv2Stream

# Bound the in-memory queue so a slow syslog target applies backpressure to
# the SSE reader instead of letting memory grow without limit.
_QUEUE_MAXSIZE = 1000


class MRAv2StreamThread(threading.Thread):
    """
    Thread wrapper around MRAv2Stream.

    The SSE reader and the syslog writer run in separate threads connected by a
    bounded queue.  If the syslog target is slow the queue fills and the reader
    blocks, preventing unbounded memory growth.
    """

    def __init__(self, ent_name: str, event_forwarder: EventForwarder, **kwargs) -> None:
        self.shutdown_flag = threading.Event()
        self.ent_name = ent_name
        self.event_forwarder = event_forwarder
        self.logger = logging.getLogger(LOGGER_NAME)
        self.error: Optional[tuple] = None
        self._queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self.stream = MRAv2Stream(**kwargs)
        threading.Thread.__init__(self)

    def run(self) -> None:
        writer = threading.Thread(
            target=self._writer_loop,
            name=f"{self.name}-writer",
            daemon=True,
        )
        writer.start()
        try:
            self._reader_loop()
        finally:
            self._queue.put(None)  # sentinel: drain remaining items then stop
            writer.join(timeout=30)

    def _reader_loop(self) -> None:
        """Read SSE events and enqueue batches for the writer thread."""
        self.logger.info(
            f"{self.name} - Fetching {self.stream.event_type} events "
            f"starting at id: {self.stream.last_event_id} or time: {self.stream.start_time}"
        )
        try:
            for event in self.stream.listenForEvents():
                if self.shutdown_flag.is_set():
                    self.stream.shutdown()
                    return

                if event.event == "events":
                    try:
                        mra_events = json.loads(event.data).get("events", [])
                    except (json.JSONDecodeError, ValueError) as e:
                        self.logger.error(
                            f"{self.name} - JSON parse failure, batch dropped. "
                            f"Error: {e}. Raw data: {event.data!r:.500}"
                        )
                        continue

                    if mra_events:
                        self.logger.debug(f"{self.name} - received {len(mra_events)} event(s)")
                        self._queue.put(mra_events)  # blocks when queue is full (backpressure)

                elif event.event == "heartbeat":
                    self.logger.debug(f"{self.name} - received heartbeat")

            self.stream.shutdown()
        except Exception as e:
            self.logger.error(f"{self.name} - Exception in stream thread: {str(e)}")
            self.error = sys.exc_info()

    def _writer_loop(self) -> None:
        """Drain the event queue and forward batches to syslog."""
        while True:
            batch = self._queue.get()
            if batch is None:  # sentinel
                break
            try:
                self.event_forwarder.write_all(batch, self.ent_name)
            except Exception as e:
                self.logger.error(f"{self.name} - Failed to forward event batch: {e}")
