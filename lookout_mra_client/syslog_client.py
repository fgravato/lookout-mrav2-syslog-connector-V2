import logging
import socket
import threading
from logging.handlers import SysLogHandler

from .lookout_logger import LOGGER_NAME


class _SysLogHandler(SysLogHandler):
    """
    SysLogHandler that surfaces errors to the connector log instead of
    swallowing them silently via the default handleError().

    Also fixes the TCP record delimiter: Python 3.3+ rewrote emit() to use
    append_nul instead of log_format_string, so patching log_format_string
    has no effect on modern Python.  We override emit() directly for TCP to
    use \\n framing (required by rsyslog imtcp and RFC-6587 octet-stuffing)
    and to remove the 1024-byte UDP cap that would silently truncate LEEF
    events.  UDP path is left to super().emit() unchanged.
    """

    def __init__(self, internal_logger, *args, **kwargs):
        self._internal_logger = internal_logger
        self._is_tcp = kwargs.get("socktype", socket.SOCK_DGRAM) == socket.SOCK_STREAM
        super().__init__(*args, **kwargs)

    def emit(self, record):
        if self._is_tcp:
            try:
                msg = self.format(record)
                prio = '<%d>' % self.encodePriority(
                    self.facility, self.mapPriority(record.levelname))
                data = (prio + msg + '\n').encode('utf-8')
                self.socket.sendall(data)
            except Exception:
                self.handleError(record)
        else:
            super().emit(record)

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

    If the syslog target is not reachable at startup the connect error is
    logged and the handler is NOT added.  Every subsequent write() checks
    whether a handler exists and retries the connection transparently, so
    events are forwarded as soon as the target becomes available without
    requiring a connector restart.
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
        self._socktype = socktype
        self.internal_logger = logging.getLogger(LOGGER_NAME)

        self.syslog_logger = logging.getLogger(name)
        self.syslog_logger.propagate = False
        self.syslog_logger.setLevel(logging.INFO)

        self._try_connect()

    def _try_connect(self) -> bool:
        """Attempt to connect to the syslog target.  Returns True on success."""
        try:
            handler = _SysLogHandler(
                self.internal_logger,
                address=self.syslog_address,
                socktype=self._socktype,
            )
            handler.formatter = logging.Formatter("%(message)s")
            with self.lock:
                # Clear any stale handlers before adding the new one.
                for h in list(self.syslog_logger.handlers):
                    try:
                        h.close()
                    except Exception:
                        pass
                    self.syslog_logger.removeHandler(h)
                self.syslog_logger.addHandler(handler)
            self.internal_logger.info(f"SyslogClient connected to {self.syslog_address}")
            return True
        except Exception as e:
            self.internal_logger.error(
                f"SyslogClient failed to connect to {self.syslog_address}: {e}"
            )
            return False

    def write(self, event: dict) -> None:
        # Lazy reconnect: if no handler exists (initial connect failed or
        # the handler was closed externally), attempt to reconnect now.
        if not self.syslog_logger.handlers:
            if not self._try_connect():
                # Still can't connect — log the event internally if requested
                # so it isn't silently lost, then return.
                if self.log_internally:
                    try:
                        event_text = self.event_formatter(event)
                        self.internal_logger.warning(
                            f"Syslog unreachable, event dropped: {event_text}"
                        )
                    except Exception:
                        pass
                return

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
