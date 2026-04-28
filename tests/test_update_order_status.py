"""
Test Suite: Update Order Status — PUT /orders/{order_id}/status
================================================================
Covers all scenarios for the order status update endpoint.

Test classes and their purpose:
    TestUpdateOrderStatusHappyPath    — valid transitions that should succeed (200)
    TestUpdateOrderStatusInvalidValues — invalid status values (400/422)
    TestUpdateOrderTerminalStates      — business rule: terminal state protection (409)
    TestUpdateOrderStatusNotFound      — updates to non-existent orders (404)
    TestUpdateOrderStatusAuthentication — requests with auth issues (401)

Terminal state concept:
    DELIVERED and CANCELLED are terminal states — once an order reaches
    either status, no further updates are permitted. This mirrors real OMS
    behaviour where reversing a delivered or cancelled order would corrupt
    the order history and potentially trigger incorrect billing or fulfilment.
"""

import pytest
from framework.validators.response_validator import ResponseValidator
from framework.auth.token_manager import TokenManager
from test_data.order_payloads import VALID_ORDER, VALID_STATUSES, INVALID_STATUSES


class TestUpdateOrderStatusHappyPath:
    """
    Verify that valid status transitions are accepted and persisted correctly.
    """

    def test_update_status_returns_200(self, client, created_order):
        """A valid status update must return 200 OK."""
        response = client.put(
            f"/orders/{created_order['order_id']}/status",
            {"status": "CONFIRMED"}
        )
        ResponseValidator(response).status_is(200)

    def test_update_status_reflects_new_status(self, client, created_order):
        """
        After updating, a subsequent GET must return the new status.
        Verifies the update is persisted — not just acknowledged in the response.
        This is a critical persistence check: returning 200 but not saving
        the change is a real bug that would be missed without this test.
        """
        order_id = created_order["order_id"]
        client.put(f"/orders/{order_id}/status", {"status": "CONFIRMED"})
        ResponseValidator(
            client.get(f"/orders/{order_id}")
        ).field_equals("status", "CONFIRMED")

    @pytest.mark.parametrize("status", VALID_STATUSES)
    def test_all_valid_statuses_accepted(self, client, status):
        """
        Every valid status must be accepted for a fresh order.

        Uses parametrize so each status is a separately named test — if
        SHIPPED fails but CONFIRMED passes, the report makes that immediately clear.

        Creates a fresh order per parametrized case to ensure each test
        starts from PENDING with no prior state.
        """
        order = client.post("/orders", VALID_ORDER).json()
        response = client.put(f"/orders/{order['order_id']}/status", {"status": status})
        ResponseValidator(response).status_is(200).field_equals("status", status)

    def test_update_status_returns_full_order(self, client, created_order):
        """
        The PUT response must return the complete updated order object.
        API consumers should not need to make a follow-up GET call just
        to see the result of their update.
        """
        response = client.put(
            f"/orders/{created_order['order_id']}/status",
            {"status": "PROCESSING"}
        )
        ResponseValidator(response).has_fields(
            "order_id", "customer_id", "items", "status", "total"
        )

    def test_status_update_is_persisted(self, client, created_order):
        """
        Verify persistence of a SHIPPED status specifically.
        Complements test_update_status_reflects_new_status with a different
        status value to increase confidence in the persistence layer.
        """
        order_id = created_order["order_id"]
        client.put(f"/orders/{order_id}/status", {"status": "SHIPPED"})
        ResponseValidator(
            client.get(f"/orders/{order_id}")
        ).field_equals("status", "SHIPPED")


class TestUpdateOrderStatusInvalidValues:
    """
    Verify that invalid status values are rejected with appropriate error codes.

    400 vs 422 distinction:
    - {} or missing 'status' key: 400 Bad Request (malformed request)
    - Unknown status string: 422 Unprocessable Entity (valid JSON, invalid value)
    """

    @pytest.mark.parametrize("bad_status", INVALID_STATUSES)
    def test_invalid_status_returns_422(self, client, bad_status):
        """
        Status values not in the defined list must be rejected with 422.
        Each invalid value is tested separately via parametrize so failures
        are reported per-value, not as a single combined failure.
        """
        order = client.post("/orders", VALID_ORDER).json()
        response = client.put(
            f"/orders/{order['order_id']}/status",
            {"status": bad_status}
        )
        ResponseValidator(response).status_is(422).has_field("error")

    def test_missing_status_field_returns_400(self, client, created_order):
        """
        A request body missing the 'status' field entirely must return 400.
        The field is required — its absence is a structural error, not a value error.
        """
        response = client.put(
            f"/orders/{created_order['order_id']}/status",
            {}  # Body present but status field missing
        )
        ResponseValidator(response).status_is(400).has_field("error")

    def test_empty_body_returns_400(self, client, created_order):
        """No request body at all must return 400, not a 500 server error."""
        response = client.put(
            f"/orders/{created_order['order_id']}/status",
            None
        )
        ResponseValidator(response).status_is(400)


class TestUpdateOrderTerminalStates:
    """
    Verify that terminal state orders (DELIVERED, CANCELLED) cannot be updated.

    Why 409 Conflict?
    409 indicates the request is valid but conflicts with the current
    state of the resource. The order exists, the endpoint is correct,
    the status value is valid — but the transition is not permitted
    because of the order's current state. That is a conflict, not a
    bad request or an unprocessable entity.
    """

    def test_cannot_update_delivered_order(self, client):
        """
        Once an order reaches DELIVERED, no further status updates are allowed.
        This prevents scenarios like accidentally reversing a completed delivery.
        """
        order = client.post("/orders", VALID_ORDER).json()
        order_id = order["order_id"]

        # Move order to terminal state
        client.put(f"/orders/{order_id}/status", {"status": "DELIVERED"})

        # Attempt to update a delivered order — must be rejected
        response = client.put(f"/orders/{order_id}/status", {"status": "PROCESSING"})
        ResponseValidator(response).status_is(409)

    def test_cannot_update_cancelled_order(self, client):
        """
        Once cancelled, an order cannot be reinstated or moved to another status.
        Cancellation is final — reinstating would require a new order.
        """
        order = client.post("/orders", VALID_ORDER).json()
        order_id = order["order_id"]

        client.put(f"/orders/{order_id}/status", {"status": "CANCELLED"})
        response = client.put(f"/orders/{order_id}/status", {"status": "CONFIRMED"})
        ResponseValidator(response).status_is(409)

    def test_delivered_order_keeps_status(self, client):
        """
        After a rejected update attempt on a DELIVERED order,
        verify the status remains DELIVERED — the rejection must not
        corrupt the order state in any way.
        """
        order = client.post("/orders", VALID_ORDER).json()
        order_id = order["order_id"]

        client.put(f"/orders/{order_id}/status", {"status": "DELIVERED"})
        client.put(f"/orders/{order_id}/status", {"status": "PROCESSING"})  # This should fail

        # Status must still be DELIVERED
        ResponseValidator(
            client.get(f"/orders/{order_id}")
        ).field_equals("status", "DELIVERED")


class TestUpdateOrderStatusNotFound:
    """
    Verify that update attempts on non-existent orders return 404.
    """

    def test_nonexistent_order_returns_404(self, client):
        """
        An update to an order that doesn't exist must return 404.
        The error must include a meaningful message — not just a status code.
        """
        response = client.put(
            "/orders/ORD-GHOST999/status",
            {"status": "CONFIRMED"}
        )
        ResponseValidator(response).status_is(404).has_field("error")


class TestUpdateOrderStatusAuthentication:
    """
    Verify that auth is enforced on the update endpoint — not just create/read.
    """

    def test_no_token_returns_401(self, client, created_order):
        """Write operations without a token must be rejected."""
        response = client.without_token().put(
            f"/orders/{created_order['order_id']}/status",
            {"status": "CONFIRMED"}
        )
        ResponseValidator(response).status_is(401)

    def test_expired_token_returns_401(self, client, created_order):
        """An expired token must be rejected on update endpoints too."""
        expired_token = TokenManager().get_expired_token()
        response = client.with_token(expired_token).put(
            f"/orders/{created_order['order_id']}/status",
            {"status": "CONFIRMED"}
        )
        ResponseValidator(response).status_is(401)
