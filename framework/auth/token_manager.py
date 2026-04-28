"""
TokenManager — JWT Authentication Handler
==========================================
Responsibility:
    Generate, cache, and manage JWT tokens for authenticating
    with the OMS API during test execution.

Why JWT?
    JWT (JSON Web Token) is the industry standard for stateless API
    authentication. A signed token carries claims (who the user is,
    when the token expires) and can be verified by the server without
    a database lookup. This mirrors how real-world API auth works.

Why a dedicated class?
    Keeping auth logic here means tests never think about tokens —
    they just get a client that works. If the auth mechanism changes
    (e.g. switching from JWT to API key), only this file changes.
"""

import jwt
import time

# Shared secret used to sign tokens here and verify them in the mock server.
# In production this would come from environment config, never hardcoded.
SECRET = "oms-test-secret-key"
ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 3600  # Tokens are valid for 1 hour


class TokenManager:
    """
    Generates and caches JWT tokens for the test session.

    Caching avoids regenerating a token on every test — which would
    be wasteful and slow. The cache is invalidated 60 seconds before
    expiry to prevent edge-case failures on slow CI runners.
    """

    # Class-level cache shared across all instances in a session
    _cached_token: str = None
    _expires_at: float = 0

    def get_token(self) -> str:
        """
        Return a valid JWT token, generating a new one if needed.

        The 60-second buffer before expiry prevents race conditions
        where a token is valid when generated but expires mid-test.
        """
        if self._cached_token and time.time() < self._expires_at - 60:
            return self._cached_token

        now = int(time.time())
        payload = {
            "sub": "qa-test-user",   # Subject — who the token belongs to
            "iat": now,               # Issued at — when the token was created
            "exp": now + TOKEN_TTL_SECONDS,  # Expiry — when it stops being valid
            "roles": ["qa", "read", "write"]  # Claims — what the user can do
        }

        self._cached_token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
        self._expires_at = now + TOKEN_TTL_SECONDS
        return self._cached_token

    def get_expired_token(self) -> str:
        """
        Generate a token that is already expired.

        Used specifically in authentication failure test cases to verify
        that the API correctly rejects expired tokens with a 401 response.

        Why not wait for a real token to expire?
        Waiting would make tests slow and timing-dependent. Generating
        an expired token on demand keeps tests fast and deterministic.
        """
        payload = {
            "sub": "qa-test-user",
            "iat": int(time.time()) - 7200,  # Issued 2 hours ago
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
        }
        return jwt.encode(payload, SECRET, algorithm=ALGORITHM)
