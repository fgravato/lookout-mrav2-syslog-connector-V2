import logging, requests
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from .lookout_logger import LOGGER_NAME

OAUTH2_ROUTE = "/oauth2/token"


class OAuthException(Exception):
    pass


class BearerAuth(requests.auth.AuthBase):
    """
    Class to create a bearer auth'ed https request
    """

    def __init__(self, token: str) -> None:
        self.token = token

    def __call__(self, r: requests.Request) -> requests.Request:
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r


class OAuth2Client:
    """
    Class OAuth2Client to authenticate with Lookout using OAuth2
    """

    def __init__(self, client_id: str, api_domain: str, api_key: str, proxies: dict = None) -> None:
        self.client_id = client_id
        self.api_domain = api_domain
        self.api_key = api_key
        self.proxies = proxies

        self.logger = logging.getLogger(LOGGER_NAME)
        self.session = OAuth2Session(client=BackendApplicationClient(self.client_id))

    def fetchAccessToken(self) -> None:
        """
        Fetch a new access token for the Requests session

        Raises:
            OauthException: If token fetch fails
        """
        try:
            self.logger.debug("Fetching new access token...")
            self.session.fetch_token(
                token_url=self.api_domain + OAUTH2_ROUTE,
                auth=BearerAuth(self.api_key),
                proxies=self.proxies,
                verify=True,
            )
        except Exception as e:
            self.logger.error(f"Exception while requesting new access token: {e}")
            raise OAuthException("Failed to retrieve token based on given api key")
