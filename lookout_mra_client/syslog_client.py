import logging, socket, threading
from logging.handlers import SysLogHandler

from .lookout_logger import LOGGER_NAME


class SyslogClient(object):
    """
    Generic Syslog client used to emit MRA events
    """

    def __init__(
        self,
        name: str,
        event_formatter: callable,
        syslog_address: tuple = ("localhost", 514),
        log_internally: bool = False,
        socktype=socket.SOCK_STREAM,
    ) -> None:
        """
        Create a Syslog client which can write data to a local or remote syslog receiver

        Args:
            name (str): Syslog client name.
            event_formatter (callable): A callable that formats a single event.
            syslog_address (tuple, optional): Address of syslog receiver. Defaults to ("localhost", 514).
            log_internally (bool, optional): Log to internal log file if true. Defaults to False.
        """

        self.lock = threading.Lock()
        self.event_formatter = event_formatter
        self.syslog_address = syslog_address
        self.log_internally = log_internally

        self.syslog_logger = logging.getLogger(name)
        self.syslog_logger.propagate = False
        self.syslog_logger.setLevel(logging.INFO)

        handler = SysLogHandler(address=self.syslog_address, socktype=socktype)
        handler.formatter = logging.Formatter("%(message)s")
        self.syslog_logger.addHandler(handler)

        self.internal_logger = logging.getLogger(LOGGER_NAME)

    def write(self, event: dict) -> None:
        """
        Apply event format and write the event to syslog.

        Args:
            event (dict): Event to be written.
        """

        event_text = self.event_formatter(event)

        with self.lock:
            self.syslog_logger.info(event_text)
            if self.log_internally:
                self.internal_logger.debug(f"{event_text}\r\n")
