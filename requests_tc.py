"""TcEx Framework Module"""

# standard library
import logging
from functools import cached_property

from ..app.config.install_json import InstallJson
from ..input.model.module_requests_session_model import ModuleRequestsSessionModel
from ..pleb.proxies import proxies
from ..pleb.scoped_property import scoped_property
from ..registry import registry
from .auth.hmac_auth import HmacAuth
from .auth.tc_auth import TcAuth
from .auth.token_auth import TokenAuth
from .tc_session import TcSession

# get logger
_logger = logging.getLogger(__name__.split('.', maxsplit=1)[0])


class RequestsTc:
    """Requests Session Class"""

    def __init__(self, model: ModuleRequestsSessionModel):
        """Initialize instance properties."""
        self.model = model

        # properties
        self.install_json = InstallJson()
        self.log = _logger

    def get_session(
        self,
        auth: HmacAuth | TokenAuth | TcAuth | None = None,
        base_url: str | None = None,
        log_curl: bool | None = None,
        proxies: dict[str, str] | None = None,  # pylint: disable=redefined-outer-name
        proxies_enabled: bool | None = None,
        verify: bool | str | None = None,
    ) -> TcSession:
        """Return an instance of Requests Session configured for the ThreatConnect API.

        No args are required to get a working instance of TC Session instance.

        This method allows for getting a new instance of TC Session instance. This can be
        very useful when connecting between multiple TC instances (e.g., migrating data).
        """
        if log_curl is None:
            log_curl = self.model.tc_log_curl

        if proxies_enabled is None:
            proxies_enabled = self.model.tc_proxy_tc

        if verify is None:
            verify = self.model.tc_verify

        tc_token = None
        # 1. if token module is available, use token callback
        # 2. if token is set in the model, use that (no renewal)
        # 3. no token is not available, use api credentials
        if hasattr(registry.app, 'token') and self.install_json.is_external_app is False:
            # token module is only available on tcex, not tcex-app-testing, or tcex-cli
            tc_token = registry.app.token.get_token  # type: ignore
        elif self.model.tc_token is not None:
            tc_token = self.model.tc_token

        auth = auth or TcAuth(
            tc_api_access_id=self.model.tc_api_access_id,
            tc_api_secret_key=self.model.tc_api_secret_key,
            tc_token=tc_token,
        )

        return TcSession(
            auth=auth,
            base_url=base_url or self.model.tc_api_path,
            log_curl=log_curl,
            proxies=proxies or self.proxies,
            proxies_enabled=proxies_enabled,
            user_agent=registry.app.user_agent,  # type: ignore
            verify=verify,
        )

    @cached_property
    def proxies(self) -> dict:
        """Return proxies dictionary for use with the Python Requests module."""
        return proxies(
            proxy_host=self.model.tc_proxy_host,
            proxy_port=self.model.tc_proxy_port,
            proxy_user=self.model.tc_proxy_username,
            proxy_pass=self.model.tc_proxy_password,
        )

    @scoped_property
    def session(self) -> TcSession:
        """Return an instance of Requests Session configured for the ThreatConnect API."""
        return self.get_session()
