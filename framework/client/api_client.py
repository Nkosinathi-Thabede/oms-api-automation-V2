"""
APIClient — Reusable HTTP Client
=================================
Responsibility:
    Wrap the requests library to provide a consistent, reusable HTTP
    interface for all test interactions with the OMS API.

Why a wrapper instead of calling requests directly?
    If tests called requests.get() / requests.post() directly:
    - A base URL change would require updating every test file
    - Adding a new required header would require updating every test file
    - Auth logic would be scattered across tests

    With this wrapper, those concerns live in one place.
    A URL change = update one line. A new header = update one method.

Auth swap pattern:
    with_token() and without_token() return new client instances with
    different auth configurations. This makes auth test cases read like
    plain English:

        client.without_token().post("/orders", payload)
        client.with_token(expired_token).get("/orders/123")
"""

import requests
import logging

logger = logging.getLogger(__name__)


class APIClient:
    """
    HTTP client for OMS API interactions.

    Wraps requests.Session to handle base URL composition,
    authentication headers, and logging in one place.
    """

    def __init__(self, base_url: str, token: str = None):
        """
        Initialise the client with a base URL and optional auth token.

        Args:
            base_url: Root URL for all API calls (e.g. http://localhost:5050)
            token:    JWT bearer token. If None, no Authorization header is set.
                      This is intentional — some tests need to verify unauthenticated behaviour.
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        if token:
            # Set auth and content headers on the session so every request
            # inherits them automatically — no need to pass headers per call
            self.session.headers.update({
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            })

    def _url(self, path: str) -> str:
        """Compose the full URL from the base URL and a relative path."""
        return f"{self.base_url}/{path.lstrip('/')}"

    def get(self, path: str, params: dict = None) -> requests.Response:
        """Send a GET request. Params are appended as query string."""
        url = self._url(path)
        logger.info(f"GET {url} params={params}")
        response = self.session.get(url, params=params)
        logger.info(f"← {response.status_code}: {response.text[:200]}")
        return response

    def post(self, path: str, payload: dict = None) -> requests.Response:
        """Send a POST request with a JSON body."""
        url = self._url(path)
        logger.info(f"POST {url} body={payload}")
        response = self.session.post(url, json=payload)
        logger.info(f"← {response.status_code}: {response.text[:200]}")
        return response

    def put(self, path: str, payload: dict = None) -> requests.Response:
        """Send a PUT request with a JSON body."""
        url = self._url(path)
        logger.info(f"PUT {url} body={payload}")
        response = self.session.put(url, json=payload)
        logger.info(f"← {response.status_code}: {response.text[:200]}")
        return response

    def with_token(self, token: str) -> "APIClient":
        """
        Return a new APIClient instance using a different token.

        Used in auth tests to verify the API rejects expired or invalid tokens.
        Returns a new instance rather than mutating the existing one —
        this keeps the shared session-scoped client unchanged.
        """
        return APIClient(base_url=self.base_url, token=token)

    def without_token(self) -> "APIClient":
        """
        Return a new APIClient instance with no Authorization header.

        Used to verify that unauthenticated requests are correctly rejected
        with a 401 response.
        """
        return APIClient(base_url=self.base_url, token=None)
