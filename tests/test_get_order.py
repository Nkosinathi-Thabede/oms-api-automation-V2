"""
Test Suite: Get Order — GET /orders/{order_id}
===============================================
Covers all scenarios for the order retrieval endpoint.

Test classes and their purpose:
    TestGetOrderHappyPath       — valid retrievals that should succeed (200)
    TestGetOrderNotFound        — requests for non-existent orders (404)
    TestGetOrderAuthentication  — requests with auth issues (401)
"""

from framework.validators.response_validator import ResponseValidator
from framework.auth.token_manager import TokenManager


class TestGetOrderHappyPath:
    """
    Verify that existing orders can be retrieved correctly.

    Uses the function-scoped created_order fixture to ensure each test
    works with a fresh, known order — not one left over from another test.
    """

    def test_get_order_returns_200(self, client, created_order):
        """A request for an existing order must return 200 OK."""
        response = client.get(f"/orders/{created_order['order_id']}")
        ResponseValidator(response).status_is(200)

    def test_get_order_returns_correct_id(self, client, created_order):
        """
        The returned order must have the same ID as the one requested.
        Verifies the server is not returning a different order by mistake.
        """
        order_id = created_order["order_id"]
        response = client.get(f"/orders/{order_id}")
        ResponseValidator(response).status_is(200).field_equals("order_id", order_id)

    def test_get_order_returns_all_fields(self, client, created_order):
        """
        The response must include all fields required to display and
        process the order. A field missing from GET but present on POST
        would break any UI or downstream system relying on the data.
        """
        response = client.get(f"/orders/{created_order['order_id']}")
        ResponseValidator(response).has_fields(
            "order_id", "customer_id", "items",
            "shipping_address", "status", "total", "created_at"
        )

    def test_get_order_status_is_pending_on_creation(self, client, created_order):
        """
        A freshly created order retrieved via GET must still be PENDING.
        Verifies that the status set on creation is persisted correctly.
        """
        response = client.get(f"/orders/{created_order['order_id']}")
        ResponseValidator(response).field_equals("status", "PENDING")

    def test_get_order_response_is_json(self, client, created_order):
        """Content-Type header must indicate JSON — same reasoning as create tests."""
        response = client.get(f"/orders/{created_order['order_id']}")
        ResponseValidator(response).content_type_is_json()

    def test_get_order_items_are_preserved(self, client, created_order):
        """
        The number of items returned must match the number sent on creation.
        Verifies that line items are stored and retrieved correctly,
        not truncated or duplicated.
        """
        response = client.get(f"/orders/{created_order['order_id']}")
        assert len(response.json()["items"]) == len(created_order["items"])


class TestGetOrderNotFound:
    """
    Verify that requests for non-existent orders return 404.

    404 Not Found is the correct HTTP semantic for a missing resource.
    The response must also include an error field — a bare 404 with
    no body is unhelpful to API consumers.
    """

    def test_nonexistent_order_returns_404(self, client):
        """A completely fabricated order ID must return 404."""
        response = client.get("/orders/ORD-DOESNOTEXIST")
        ResponseValidator(response).status_is(404).has_field("error")

    def test_random_id_returns_404(self, client):
        """An ID in the correct format but never created must return 404."""
        response = client.get("/orders/ORD-00000000")
        ResponseValidator(response).status_is(404)

    def test_404_response_contains_error_field(self, client):
        """
        The 404 response must include an 'error' field.
        A plain 404 with an empty body forces API consumers to handle
        the case with no information about what went wrong.
        """
        response = client.get("/orders/ORD-FAKE999")
        ResponseValidator(response).status_is(404).has_field("error")


class TestGetOrderAuthentication:
    """
    Verify that unauthenticated and invalidly authenticated GET requests
    are rejected before any order data is returned.

    Auth must be enforced on read endpoints — not just write endpoints.
    """

    def test_no_token_returns_401(self, client, created_order):
        """
        A GET request with no token must return 401.
        Verifies that read access is protected — not just create/update.
        """
        response = client.without_token().get(f"/orders/{created_order['order_id']}")
        ResponseValidator(response).status_is(401)

    def test_expired_token_returns_401(self, client, created_order):
        """An expired token must be rejected even on read requests."""
        expired_token = TokenManager().get_expired_token()
        response = client.with_token(expired_token).get(
            f"/orders/{created_order['order_id']}"
        )
        ResponseValidator(response).status_is(401)
