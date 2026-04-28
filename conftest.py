"""
conftest.py — Shared Pytest Fixtures
======================================
Fixtures defined here are automatically available to every test file
without needing to be imported. This is pytest's built-in mechanism
for shared setup and teardown.

Fixture scopes used here:
    session  — created once for the entire test run, shared by all tests.
               Used for the mock server, token, and client — expensive
               to create and safe to share.

    function — created fresh for each individual test function.
               Used for created_order — each test that needs an order
               gets a brand new PENDING one, preventing state leakage
               between tests.

Why function scope for created_order?
    If one test moves an order to DELIVERED and another test then tries
    to update it, the second test would fail for the wrong reason.
    Function scope guarantees each test starts with a clean, PENDING order.
"""

import pytest
import subprocess
import time
import requests
import sys

from framework.auth.token_manager import TokenManager
from framework.client.api_client import APIClient

# The base URL where the mock server listens during the test session
BASE_URL = "http://localhost:5050"


def wait_for_server(url: str, retries: int = 10, delay: float = 0.5) -> bool:
    """
    Poll the server's /health endpoint until it responds or retries are exhausted.

    Why poll instead of just sleeping for a fixed time?
    A fixed sleep is fragile — too short fails on slow machines,
    too long wastes time. Polling starts tests as soon as the server
    is genuinely ready, and fails fast if something went wrong.
    """
    for _ in range(retries):
        try:
            requests.get(f"{url}/health", timeout=1)
            return True
        except Exception:
            time.sleep(delay)
    return False


@pytest.fixture(scope="session", autouse=True)
def mock_server():
    """
    Start the Flask mock server before any tests run, stop it after all tests finish.

    scope="session"  — server starts once per test run, not once per test
    autouse=True     — applied automatically to every test, no need to request it

    The server runs as a subprocess (a separate OS process) so it has
    its own network stack and receives real HTTP requests — not mocked ones.
    """
    proc = subprocess.Popen(
        [sys.executable, "mock_server/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for the server to be ready before releasing control to tests
    if not wait_for_server(BASE_URL):
        proc.terminate()
        raise RuntimeError(
            "Mock server did not start in time. "
            "Check mock_server/server.py for errors."
        )

    yield proc  # Tests run here

    # Teardown — cleanly terminate the server process after all tests finish
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session")
def token():
    """
    Generate a JWT token once for the entire session.

    Shared across all tests that need auth — avoids regenerating
    a token for each of the 52 test cases.
    """
    return TokenManager().get_token()


@pytest.fixture(scope="session")
def client(token):
    """
    Provide a configured APIClient for the entire test session.

    Session-scoped because creating an HTTP session is relatively
    expensive and the client is stateless between requests.
    """
    return APIClient(base_url=BASE_URL, token=token)


@pytest.fixture
def created_order(client):
    """
    Create a fresh order and return it for use in a single test.

    Function-scoped (default) — a new order is created for each test
    that requests this fixture. This prevents state leakage:
    - If test A moves an order to DELIVERED, test B gets a fresh PENDING order
    - Tests are fully independent regardless of execution order

    The assertion here is a pre-condition check — if order creation
    itself is broken, this fixture fails immediately with a clear message
    rather than causing confusing failures in the dependent test.
    """
    payload = {
        "customer_id": "CUST-FIXTURE-001",
        "items": [{"sku": "ITEM-A", "quantity": 2, "price": 49.99}],
        "shipping_address": {
            "line1": "123 Main St",
            "city": "Cape Town",
            "postal_code": "8001",
            "country": "ZA"
        }
    }
    response = client.post("/orders", payload)

    # Pre-condition: order creation must succeed before the test can run
    assert response.status_code == 201, (
        f"created_order fixture failed — POST /orders returned {response.status_code}: "
        f"{response.text}"
    )
    return response.json()
