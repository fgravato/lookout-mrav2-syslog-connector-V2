"""
Module OauthClient to authenticate services with Lookout's backend
"""

import json
import logging
import requests

from .lookout_logger import LOGGER_NAME


OAUTH_ROUTE = "/oauth/token"
STALE_TOKEN_STATUS_CODES = [400, 401]
STALE_TOKEN_ERRORS = ["REVOKED_REFRESH_TOKEN", "EXPIRED_TOKEN"]


class OauthException(Exception):
    pass


class OauthClient:
    """
    Class OauthClient to authenticate a service with Lookout's backend
    """

    def __init__(self, api_domain: str, api_key: str, proxies: dict = None) -> None:
        """
        Construct a new OauthClient to authenticate a service with Lookout's backend

        Args:
            api_domain (str): i.e. https://api.today.lookoutqa.com
            api_key (str): API Key generated from MES.
            proxies (dict, optional): Proxy connection dict. Defaults to None.
        """
        self.api_domain = api_domain
        self.api_key = api_key
        self.access_token = ""
        self.proxies = proxies

        self.logger = logging.getLogger(LOGGER_NAME)

    def base_header(self) -> dict:
        """
        Format request headers

        Returns:
            dict: Base headers
        """
        return {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        }

    def token_header(self, token: str) -> dict:
        """
        Format request headers with authentication

        Args:
            token (str): Auth token

        Returns:
            dict: Authenticated headers
        """
        header = self.base_header()
        header["Authorization"] = "Bearer {}".format(token)
        return header

    def get_oauth(self) -> None:
        """
        Retrieve OAuth tokens from Lookout API.

        Stores the access_token in this object.
        If the access token is already stored, do nothing.

        Raises:
            OauthException: If request for oauth fails.
        """
        token_json = {}
        if self.access_token:
            self.logger.info("The access token has been found locally")
            return

        self.logger.info("No access token found locally, requesting one now")
        response = requests.post(
            self.api_domain + OAUTH_ROUTE,
            data="grant_type=client_credentials",
            headers=self.token_header(self.api_key),
            proxies=self.proxies,
        )

        try:
            token_json = json.loads(response.text)

            self.access_token = token_json["access_token"]
        except (AttributeError, ValueError, KeyError) as e:
            self.logger.error("Exception when requesting new access token: {}".format(e))
            self.logger.error("Raw response: {}".format(response.text))
            raise OauthException("Failed to retrieve tokens based on the given api key")
