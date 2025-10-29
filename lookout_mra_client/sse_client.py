import logging, requests
from typing import Generator

from requests_oauthlib import OAuth2Session

from .lookout_logger import LOGGER_NAME
from .server_sent_event import SSEvent

SSE_DELIMITER = (b"\r\r", b"\n\n", b"\r\n\r\n")
SSE_FIELD_SEP = ":"
SSE_DEFAULT_TIMEOUT = 5  # seconds


def streamRequest(
    url: str,
    session: OAuth2Session = None,
    headers: dict = {},
    params: dict = {},
    proxies: dict = {},
    timeout: int = SSE_DEFAULT_TIMEOUT,
    user_agent: str = "SSEClient",
) -> requests.Response:
    """
    Create a streaming requests.Request to be used by the SSE client.

    Args:
        url (str): SSE Server url
        headers (dict): Request headers
        params (dict): MRAv2 parameters
        proxies (dict): Dict of proxy endpoints in requests format
        timeout (int): Request timeout. Defaults to SSE_DEFAULT_TIMEOUT (5 seconds)

    Returns:
        requests.Response: Streaming request connecting to MRAv2
    """

    headers["Accept"] = "text/event-stream"
    headers["Cache-Control"] = "no-cache"
    headers["User-Agent"] = user_agent

    requester = session or requests
    return requester.get(
        url, stream=True, headers=headers, params=params, proxies=proxies, timeout=timeout
    )


class SSEClient:
    """
    Python Server Sent Event client for streaming events from an SSE server,
    based on the HTML spec for Server Sent Events.

    Specification: https://html.spec.whatwg.org/multipage/server-sent-events.html#server-sent-events
    """

    def __init__(self, event_stream: requests.Response, event_enc: str = "utf-8"):
        self.event_stream = event_stream
        self.event_enc = event_enc
        self.logger = logging.getLogger(LOGGER_NAME)

    def __read(self) -> Generator[bytes, None, None]:
        """
        Read from the event stream and yield raw event data.

        Yields:
            bytes: Raw event bytes
        """
        raw_event = b""
        # NOTE: requests.Response.__iter__() uses request.Response.iter_content(128)
        for event_part in self.event_stream:
            # NOTE: splitlines(True) splits the line, but preserves the line ending character(s)
            #   Is necessary so we can parse the SSE delimiter.
            for line in event_part.splitlines(True):
                raw_event += line
                if raw_event.endswith(SSE_DELIMITER):
                    yield raw_event
                    raw_event = b""

    def streamEvents(self) -> Generator[SSEvent, None, None]:
        """
        Stream events from a SSE endpoint

        Yields:
            SSEvent: Server Sent Event
        """
        for raw_event in self.__read():
            event = SSEvent()
            for line in raw_event.splitlines():
                line = line.decode(self.event_enc)
                # NOTE: Spec states:
                #   If the line is empty (a blank line), Dispatch the event, as defined below.
                #   If the line starts with a U+003A COLON character (:), Ignore the line.
                if (
                    not line.strip()
                    or line.startswith(SSE_FIELD_SEP)
                    or (SSE_FIELD_SEP not in line)
                ):
                    continue

                # NOTE: line is '<field_name>: <value>'
                #   only split once to preserve `:` characters in value
                (field, value) = line.split(SSE_FIELD_SEP, 1)
                try:
                    event.append(field, value.strip())
                except ValueError as e:
                    self.logger.warning(str(e))
            # remove the last newline appended to data section
            event.data = event.data.strip()

            if not event.blank():
                yield event
        self.close()

    def close(self) -> None:
        """
        Close the event stream.
        """
        self.event_stream.close()
