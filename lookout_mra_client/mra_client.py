"""
Module MRAClient to collect events from the Lookout Mobile Risk API.
"""

import logging
import requests
from datetime import datetime

from .lookout_logger import LOGGER_NAME
from .oauth_client import OauthClient, STALE_TOKEN_STATUS_CODES, STALE_TOKEN_ERRORS
from . import __prj_name__


class MRAClient:
    """
    Class MRAClient to collect events from the Lookout Mobile Rish API.
    """

    def __init__(
        self,
        api_domain: str,
        api_key: str,
        stream_position: int = 0,
        start_time: datetime = None,
        event_type: str = "THREAT,DEVICE",
        proxies: dict = None,
        user_agent: str = None,
    ) -> None:
        self.api_domain = api_domain
        self.api_key = api_key
        self.stream_position = stream_position
        self.start_time = start_time
        self.event_type = event_type
        self.proxies = proxies
        if user_agent is None:
            self.user_agent = f"{__prj_name__}"
        else:
            self.user_agent = f"{user_agent}; {__prj_name__}"

        self.oauth = OauthClient(api_domain, api_key, self.proxies)
        self.logger = logging.getLogger(LOGGER_NAME)

    def get_events(self, limit: int = 100) -> list:
        """
        Method to collect events from Mobile Risk API
        - Requests events (retries if error HTTP code)
        - Collect events lists from the Mobile Risk API
        """
        if not self.oauth.access_token:
            self.oauth.get_oauth()

        events = []
        retry_count = 0
        count = 0
        more_events = True
        while more_events and count < limit and retry_count < 10:
            params = {
                "eventType": self.event_type,
                "limit": limit,
            }

            if (isinstance(self.stream_position, int) and self.stream_position >= 0) or (
                isinstance(self.stream_position, str) and self.stream_position == "now"
            ):
                params["streamPosition"] = self.stream_position
            elif self.start_time is not None:
                params["startTime"] = self.start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            headers = self.oauth.token_header(self.oauth.access_token)
            headers["User-Agent"] = self.user_agent

            response = requests.get(
                self.api_domain + "/events",
                headers=headers,
                params=params,
                proxies=self.proxies,
            )
            resp_json = response.json()

            if (
                response.status_code in STALE_TOKEN_STATUS_CODES
                and resp_json["errorCode"] in STALE_TOKEN_ERRORS
            ):
                self.oauth.access_token = ""
                self.oauth.get_oauth()
                continue
            elif response.status_code != requests.codes.ok:
                self.logger.info(
                    "Received error code {}, trying again to get events".format(
                        response.status_code
                    )
                )
                retry_count = retry_count + 1
                continue

            response_events = resp_json["events"]
            count = count + len(response_events)
            events = events + response_events
            more_events = resp_json["moreEvents"]

            self.stream_position = int(resp_json["streamPosition"])

        if retry_count >= 10:
            self.logger.error("Too many failed attempts to retrieve events, retrying later.")
            return events

        return events
