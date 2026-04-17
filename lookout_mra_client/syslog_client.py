import logging
import socket
import threading
from logging.handlers import SysLogHandler

from .lookout_logger import LOGGER_NAME


class _SysLogHandler(SysLogHandler):
    """
    SysLogHandler that surfaces errors to the connector log instead of
    swallowing them silently via the default handleError().

    Also fixes the TCP record delimiter: Python's SysLogHandler appends
    \\000 (null) which rsyslog imtcp never flushes because it expects \\n.
    We override the format string to use \\n for TCP and keep \\000 for UDP
    (UDP datagrams are self-delimiting so the terminator doesn't matter).
    """

    # Default format used by SysLogHandler for all socket types.
    # We patch it per-instance in __init__ based on socktype.
    log_format_string = '<%d>%s\000'

    def __init__(self, internal_logger, *args, **kwargs):
        self._internal_logger = internal_logger
        socktype = kwargs.get("socktype", socket.SOCK_DGRAM)
        super().__init__(*args, **kwargs)
        # rsyslog imtcp (and most RFC-3164 TCP receivers) use newline framing;
        # the null terminator causes messages to accumulate and never flush.
        if socktype == socket.SOCK_STREAM:
            self.log_format_string = '<%d>%s\n'

    def handleError(self, record):
        import traceback
        self._internal_logger.error(
            f"SysLogHandler failed to send event: {traceback.format_exc()}"
        )


class SyslogClient(object):
    """
    Generic Syslog client used to emit MRA events.
    Uses Python's SysLogHandler (correct syslog framing) with explicit
    error logging so failures are never swallowed silently.
    """

    def __init__(
        self,
        name: str,
        event_formatter: callable,
        syslog_address: tuple = ("localhost", 514),
        log_internally: bool = False,
        socktype=socket.SOCK_STREAM,
    ) -> None:
        self.lock = threading.Lock()
        self.event_formatter = event_formatter
        self.syslog_address = syslog_address
        self.log_internally = log_internally
        self.internal_logger = logging.getLogger(LOGGER_NAME)

        self.syslog_logger = logging.getLogger(name)
        self.syslog_logger.propagate = False
        self.syslog_logger.setLevel(logging.INFO)

        try:
            handler = _SysLogHandler(
                self.internal_logger,
                address=syslog_address,
                socktype=socktype,
            )
            handler.formatter = logging.Formatter("%(message)s")
            self.syslog_logger.addHandler(handler)
            self.internal_logger.debug(f"SyslogClient connected to {syslog_address}")
        except Exception as e:
            self.internal_logger.error(f"SyslogClient failed to connect to {syslog_address}: {e}")

    def write(self, event: dict) -> None:
        event_text = self.event_formatter(event)

        with self.lock:
            self.syslog_logger.info(event_text)
            if self.log_internally:
                self.internal_logger.info(f"LEEF: {event_text}")

    def close(self) -> None:
        """Close and remove all syslog handlers, freeing the underlying socket."""
        with self.lock:
            for handler in list(self.syslog_logger.handlers):
                try:
                    handler.close()
                except Exception:
                    pass
                self.syslog_logger.removeHandler(handler)
