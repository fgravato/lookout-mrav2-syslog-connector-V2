import logging, backoff
from datetime import datetime
from typing import Generator, Tuple
from oauthlib.oauth2 import TokenExpiredError

from .lookout_logger import LOGGER_NAME
from .oauth2_client import OAuth2Client
from .sse_client import SSEClient, SSEvent, streamRequest
from . import __prj_name__

MRA_V2_STREAM_ROUTE = "/mra/stream/v2/events"
# MRA v2 sends a heartbeat at least every 5 seconds when no events to stream.
#   If no events seen in 5 seconds, close the connection and reconnect.
# NOTE: Set this to 10 seconds for now to avoid reconnecting if MRA v2 happens to be slow.
TIMEOUT = 10  # seconds
YIELD_EVENTS = ["events", "heartbeat"]
RECONNECT_EVENTS = ["end", "reconnect"]


class ShutdownException(Exception):
    pass


class MRAv2Stream:
    """
    Configure and initialize a SSE Client connected to the Mobile Risk API v2.
    """

    def __init__(
        self,
        api_domain: str,
        api_key: str,
        last_event_id: int = 0,
        start_time: datetime = None,
        event_type: str = "THREAT,DEVICE",
        proxies: dict = None,
        user_agent: str = None,
    ) -> None:
        self.last_event_id = last_event_id
        self.start_time = start_time
        self.event_type = event_type
        self.proxies = proxies
        self.retry_ms = None
        if user_agent is None:
            self.user_agent = f"{__prj_name__}"
        else:
            self.user_agent = f"{user_agent}; {__prj_name__}"

        self.endpoint = api_domain + MRA_V2_STREAM_ROUTE

        self.logger = logging.getLogger(LOGGER_NAME)
        self.oauth_client = OAuth2Client("MRAv2", api_domain, api_key, proxies)
        self.mra_v2_client: SSEClient = None

    @backoff.on_exception(backoff.expo, Exception, max_tries=5, jitter=None, logger=LOGGER_NAME)
    def __init_stream(self) -> None:
        """
        Initialize the stream client, fetching an access token if needed.
        """
        self.oauth_client.fetchAccessToken()

        params = {}
        params["types"] = self.event_type
        if self.start_time:
            params["start_time"] = self.start_time.isoformat()
        else:
            params["id"] = str(self.last_event_id)

        mra_stream = streamRequest(
            self.endpoint,
            session=self.oauth_client.session,
            params=params,
            proxies=self.proxies,
            timeout=TIMEOUT,
            user_agent=self.user_agent,
        )
        if mra_stream.status_code != 200:
            self.logger.error(
                f"Failed to connect to MRA v2, status code: {mra_stream.status_code}, response: {mra_stream.text}"
            )
            mra_stream.raise_for_status()
        self.mra_v2_client = SSEClient(mra_stream)

    @backoff.on_exception(backoff.expo, Exception, max_tries=5, jitter=None, logger=LOGGER_NAME)
    def __restart_stream(self) -> None:
        """
        Restart the stream client, fetching a new access token if needed.
        """
        self.logger.info("Restarting MRA v2 stream...")
        self.shutdown()

        self.oauth_client.fetchAccessToken()
        params = {
            "id": str(self.last_event_id),
            "types": self.event_type,
        }
        mra_stream = streamRequest(
            self.endpoint,
            session=self.oauth_client.session,
            params=params,
            proxies=self.proxies,
            timeout=TIMEOUT,
            user_agent=self.user_agent,
        )
        if mra_stream.status_code != 200:
            self.logger.error(
                f"Failed to connect to MRA v2, status code: {mra_stream.status_code}, response: {mra_stream.text}"
            )
            mra_stream.raise_for_status()
        self.mra_v2_client = SSEClient(mra_stream)

    def listenForEvents(self) -> Generator[SSEvent, None, None]:
        """
        Listen to MRAv2 for events, handles reconnects.

        NOTE: Need to yield heartbeats or else listenForEvents will stall until
        a new MRA v2 event is published.

        Yields:
            SSEvent: Either a group of MRA v2 events, or a heartbeat.
        """
        self.__init_stream()

        while True:
            try:
                for ss_event in self.mra_v2_client.streamEvents():
                    if ss_event.id:
                        self.last_event_id = ss_event.id
                    if ss_event.event in YIELD_EVENTS:
                        yield ss_event
                    elif ss_event.event in RECONNECT_EVENTS:
                        if ss_event.retry:
                            self.retry_ms = ss_event.retry
                        raise ShutdownException(
                            f"{ss_event.event} event received, shutting down..."
                        )
            except TokenExpiredError:
                self.logger.info("Access token expired, refreshing token")
                self.oauth_client.fetchAccessToken()
                continue
            except ShutdownException:
                break
            except Exception:
                self.logger.exception(f"Error fetching events from stream")

                # Restart the stream connection
                try:
                    self.__restart_stream()
                    continue
                except Exception:
                    self.logger.exception(f"Failed to restart stream. Exiting stream listener.")
                    break

        self.shutdown()

    def shutdown(self) -> Tuple[int, int]:
        """
        Report last seen event id and close SSE connection.

        Returns:
            int: Id of last event seen by the stream.s
        """
        # NOTE: The sse client connected to mra v2 will not connect if the initial request fails/timesout,
        #   therefore can only close a connection that exists.
        if self.mra_v2_client:
            self.mra_v2_client.close()
        self.logger.debug("Shutting down... Last Event Id: {}".format(self.last_event_id))
        return (self.last_event_id, self.retry_ms)
