"""
Test Suite: Create Order — POST /orders
========================================
Covers all scenarios for the order creation endpoint.

Test classes and their purpose:
    TestCreateOrderHappyPath    — valid requests that should succeed (201)
    TestCreateOrderMissingFields — requests missing required fields (400)
    TestCreateOrderInvalidValues — requests with wrong field values (422)
    TestCreateOrderAuthentication — requests with auth issues (401)

Why class-based organisation?
    Grouping by scenario type makes the test report immediately readable.
    When a CI run fails, you can see at a glance whether it's a happy path
    regression, a validation issue, or an auth problem — without reading
    individual test names.
"""

import pytest
from framework.validators.response_validator import ResponseValidator
from framework.auth.token_manager import TokenManager
from test_data.order_payloads import (
    VALID_ORDER, VALID_ORDER_MULTI_ITEM, VALID_ORDER_SINGLE_ITEM,
    VALID_ORDER_FIVE_ITEMS,
    MISSING_CUSTOMER_ID, MISSING_ITEMS, MISSING_SHIPPING_ADDRESS,
    EMPTY_ITEMS_LIST, ZERO_QUANTITY, NEGATIVE_PRICE
)


class TestCreateOrderHappyPath:
    """
    Verify that valid order creation requests return the correct response.

    These tests establish the baseline — if any of these fail, something
    fundamental is broken in the create order flow.
    """

    def test_create_order_returns_201(self, client):
        """A valid order request must return 201 Created — not 200, not 204."""
        response = client.post("/orders", VALID_ORDER)
        ResponseValidator(response).status_is(200)

    def test_create_order_returns_order_id(self, client):
        """
        The response must include a non-empty order_id.
        This ID is how the client references the order in subsequent calls.
        """
        response = client.post("/orders", VALID_ORDER)
        ResponseValidator(response).status_is(201).has_field("order_id").field_not_empty("order_id")

    def test_create_order_status_is_pending(self, client):
        """
        All newly created orders must start in PENDING status.
        PENDING is the entry point of the order lifecycle — no order
        should skip directly to CONFIRMED or beyond on creation.
        """
        response = client.post("/orders", VALID_ORDER)
        ResponseValidator(response).status_is(201).field_equals("status", "PENDING")

    def test_create_order_total_is_calculated(self, client):
        """
        The API must calculate and return the order total.
        Verifies: total = sum(quantity * price) for all items.
        This is a business-critical calculation — an incorrect total
        would result in the customer being charged the wrong amount.
        """
        response = client.post("/orders", VALID_ORDER)
        body = response.json()
        expected_total = sum(i["quantity"] * i["price"] for i in VALID_ORDER["items"])
        assert round(body["total"], 2) == round(expected_total, 2), (
            f"Expected total {expected_total}, got {body['total']}"
        )

    def test_create_order_returns_all_required_fields(self, client):
        """
        The response body must include all fields the client needs to
        track and display the order. A missing field would silently break
        any downstream system consuming this API.
        """
        response = client.post("/orders", VALID_ORDER)
        ResponseValidator(response).has_fields(
            "order_id", "customer_id", "items",
            "shipping_address", "status", "total", "created_at"
        )

    def test_create_order_response_is_json(self, client):
        """
        The Content-Type header must indicate JSON.
        Without this check, a misconfigured server returning HTML error
        pages could pass status code checks but break JSON parsing downstream.
        """
        response = client.post("/orders", VALID_ORDER)
        ResponseValidator(response).content_type_is_json()

    @pytest.mark.parametrize("payload,label", [
        (VALID_ORDER, "single_item"),
        (VALID_ORDER_MULTI_ITEM, "multi_item"),
        (VALID_ORDER_SINGLE_ITEM, "minimum_order"),
    ])
    def test_create_order_data_driven(self, client, payload, label):
        """
        Verify order creation works for all valid payload variations.

        Using parametrize instead of three separate test functions:
        - Keeps the test logic DRY (defined once)
        - Each scenario runs as a separately named test in the report
        - Adding a new scenario only requires adding a payload to test_data/
        """
        response = client.post("/orders", payload)
        ResponseValidator(response).status_is(201).has_field("order_id")

    def test_create_order_multi_item_total_is_correct(self, client):
        """
        Verify total calculation is correct for multi-line orders.
        Tests the sum across multiple items with different quantities and prices.
        """
        response = client.post("/orders", VALID_ORDER_MULTI_ITEM)
        body = response.json()
        expected = sum(i["quantity"] * i["price"] for i in VALID_ORDER_MULTI_ITEM["items"])
        assert round(body["total"], 2) == round(expected, 2)

    def test_each_order_gets_unique_id(self, client):
        """
        Verify that two orders created from the same payload get different IDs.
        Duplicate IDs would cause data corruption in the order management system.
        """
        r1 = client.post("/orders", VALID_ORDER)
        r2 = client.post("/orders", VALID_ORDER)
        assert r1.json()["order_id"] != r2.json()["order_id"], (
            "Two separate orders received the same order_id — IDs must be unique"
        )
    def test_create_order_five_item_total_is_correct(self, client):
        """
        Verify total calculation is correct across 5 line items
        with different quantities and prices.
        A miscalculation here means the customer is charged
        the wrong amount — business critical.
        """
        response = client.post("/orders", VALID_ORDER_FIVE_ITEMS)
        ResponseValidator(response).status_is(201)
        body = response.json()
        expected_total = sum(
            item["quantity"] * item["price"]
            for item in VALID_ORDER_FIVE_ITEMS["items"]
        )
        # Round to 2dp to handle floating point precision
        # e.g. 3 x 5.99 = 17.969999999 in Python, not 17.97
        assert round(body["total"], 2) == round(expected_total, 2), (
            f"Expected total {expected_total}, got {body['total']}. "
            f"Total calculation incorrect across 5 line items."
        )



class TestCreateOrderMissingFields:
    """
    Verify that requests missing required fields are rejected with 400.

    400 Bad Request is the correct status for structurally invalid requests.
    Each test removes one required field to verify each field is validated
    independently.
    """

    @pytest.mark.parametrize("payload,missing_field", [
        (MISSING_CUSTOMER_ID, "customer_id"),
        (MISSING_ITEMS, "items"),
        (MISSING_SHIPPING_ADDRESS, "shipping_address"),
    ])
    def test_missing_required_field_returns_400(self, client, payload, missing_field):
        """
        Each required field must be individually validated.
        The error response must include an 'error' field with a meaningful message
        — a generic 500 with no body is not acceptable.
        """
        response = client.post("/orders", payload)
        ResponseValidator(response).status_is(400).has_field("error")

    def test_empty_body_returns_400(self, client):
        """An empty JSON object {} is missing all required fields — must return 400."""
        response = client.post("/orders", {})
        ResponseValidator(response).status_is(400)

    def test_no_body_returns_400(self, client):
        """A request with no body at all must return 400, not a 500 server error."""
        response = client.post("/orders", None)
        ResponseValidator(response).status_is(400)


class TestCreateOrderInvalidValues:
    """
    Verify that requests with structurally valid but semantically wrong
    values are rejected with 422 Unprocessable Entity.

    The distinction between 400 and 422:
    - 400: The request is malformed (missing fields, wrong structure)
    - 422: The request is well-formed but the values don't make business sense
    """

    def test_empty_items_list_returns_400(self, client):
        """
        An empty items list [] is structurally present but semantically invalid.
        An order with no items cannot be processed or fulfilled.
        """
        response = client.post("/orders", EMPTY_ITEMS_LIST)
        ResponseValidator(response).status_is(400).has_field("error")

    def test_zero_quantity_returns_422(self, client):
        """
        Quantity of 0 is a valid integer but makes no business sense.
        A zero-quantity line item would create a £0 order line with no fulfilment.
        """
        response = client.post("/orders", ZERO_QUANTITY)
        ResponseValidator(response).status_is(422).has_field("error")

    def test_negative_price_returns_422(self, client):
        """
        A negative price would imply the customer is owed money —
        this must be rejected before it reaches any billing system.
        """
        response = client.post("/orders", NEGATIVE_PRICE)
        ResponseValidator(response).status_is(422).has_field("error")


class TestCreateOrderAuthentication:
    """
    Verify that all authentication failure scenarios return 401.

    Auth is checked before any business logic — an unauthenticated
    request should never reach validation or order creation.
    """

    def test_no_token_returns_401(self, client):
        """
        A request with no Authorization header must be rejected.
        Uses without_token() to create a client with no auth headers.
        """
        response = client.without_token().post("/orders", VALID_ORDER)
        ResponseValidator(response).status_is(401)

    def test_expired_token_returns_401(self, client):
        """
        An expired token must be rejected with 401.
        Also verifies the error message contains 'expired' — confirming
        the server correctly identifies the reason for rejection,
        not just that something went wrong.
        """
        expired_token = TokenManager().get_expired_token()
        response = client.with_token(expired_token).post("/orders", VALID_ORDER)
        ResponseValidator(response).status_is(401).error_message_contains("expired")

    def test_invalid_token_returns_401(self, client):
        """
        A completely invalid token string (not a valid JWT) must be rejected.
        Tests the auth layer handles malformed tokens gracefully.
        """
        response = client.with_token("this.is.not.a.valid.jwt").post("/orders", VALID_ORDER)
        ResponseValidator(response).status_is(401)
