"""TcEx Framework Module"""

# standard library
import contextlib
import logging

# third-party
import urllib3
from requests import Response, Session, adapters
from urllib3.util.retry import Retry

from ..util.requests_to_curl import RequestsToCurl  # type: ignore
from ..util.util import Util  # type: ignore
from .auth.hmac_auth import HmacAuth
from .auth.tc_auth import TcAuth
from .auth.token_auth import TokenAuth

# get logger
_logger = logging.getLogger(__name__.split('.', maxsplit=1)[0])

# disable ssl warning message
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # type: ignore


class TcSession(Session):
    """ThreatConnect REST API Requests Session"""

    def __init__(
        self,
        auth: HmacAuth | TokenAuth | TcAuth,
        base_url: str | None = None,
        log_curl: bool | None = False,
        proxies: dict[str, str] | None = None,
        proxies_enabled: bool | None = False,
        user_agent: dict[str, str] | None = None,
        verify: bool | str | None = True,
    ):
        """Initialize the Class properties."""
        super().__init__()
        self.base_url = base_url.strip('/') if base_url is not None else base_url
        self.log = _logger
        self.log_curl = log_curl

        # properties
        self.requests_to_curl = RequestsToCurl()
        self.util = Util()

        # configure auth
        self.auth = auth

        # configure optional headers
        if user_agent:
            self.headers.update(user_agent)

        # configure proxy
        if proxies and proxies_enabled:
            self.proxies = proxies

        # configure verify
        self.verify = verify

        # Add Retry
        self.retry()

    def _log_curl(self, response: Response):
        """Log the curl equivalent command."""

        # don't show curl message for logging commands
        # APP-79 - adding logging of request as curl commands
        # if response.request.url is not None and '/v2/logs/app' not in response.request.url:
        #     if not response.ok or self.log_curl:
        if (response.request.url is not None and '/v2/logs/app' not in response.request.url) and (
            not response.ok or self.log_curl
        ):
            with contextlib.suppress(Exception):
                self.log.debug(
                    self.requests_to_curl.convert(
                        response.request, proxies=self.proxies, verify=self.verify
                    )
                )

    def request(self, method, url, **kwargs):  # type: ignore
        """Override request method disabling verify on token renewal if disabled on session."""
        response = super().request(method, self.url(url), **kwargs)
        bad_request_code = 401

        # retry request in case we encountered a race condition with token renewal monitor
        if response.status_code == bad_request_code:
            self.log.debug(
                f'Unexpected response received while attempting to send a request using internal '
                f'session object. Retrying request. feature=tc-session, '
                f'request-url={response.request.url}, status-code={response.status_code}'
            )
            response = super().request(method, self.url(url), **kwargs)

        # optionally log the curl command
        self._log_curl(response)

        # log request and response data
        self.log.debug(
            f'feature=tc-session, method={method}, request-url={response.request.url}, '
            f'status-code={response.status_code}, elapsed={response.elapsed}'
        )

        return response

    def retry(self, retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
        """Add retry to Requests Session

        https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#urllib3.util.retry.Retry
        """
        retries = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,  # type: ignore
            status_forcelist=status_forcelist,
        )
        # mount all https requests
        self.mount('https://', adapters.HTTPAdapter(max_retries=retries))

    def url(self, url: str) -> str:
        """Return appropriate URL string.

        The method allows the session to accept the URL Path or the full URL.
        """
        if not url.startswith('https'):
            return f'{self.base_url}{url}'
        return url
