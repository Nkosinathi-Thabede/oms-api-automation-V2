"""
Test Data — Order Payloads
===========================
Responsibility:
    Centralise all test payloads in one place, completely separate
    from test logic.

Why separate test data from test code?
    If payloads were defined inline inside each test function:
    - A field name change in the API would require hunting through
      every test file to find and update every occurrence
    - Data-driven tests would have payloads scattered in parametrize
      decorators, making them hard to read and maintain

    With all data here:
    - One change propagates to every test that uses that payload
    - Test files stay focused on what they're testing, not the data
    - New scenarios are added by adding a payload here, not editing tests

Naming convention:
    VALID_*   — payloads that should succeed (2xx responses)
    MISSING_* — payloads with a required field removed (400 responses)
    INVALID_* — payloads with semantically wrong values (422 responses)
"""


# ─────────────────────────────────────────────
# Valid order payloads — expect 201 Created
# ─────────────────────────────────────────────

# Standard single-item order — used as the default happy path payload
VALID_ORDER = {
    "customer_id": "CUST-001",
    "items": [{"sku": "ITEM-A", "quantity": 2, "price": 49.99}],
    "shipping_address": {
        "line1": "123 Main St",
        "city": "Cape Town",
        "postal_code": "8001",
        "country": "ZA"
    }
}

# Multi-item order — verifies the total calculation works across multiple lines
VALID_ORDER_MULTI_ITEM = {
    "customer_id": "CUST-002",
    "items": [
        {"sku": "ITEM-A", "quantity": 1, "price": 29.99},
        {"sku": "ITEM-B", "quantity": 3, "price": 15.00},
        {"sku": "ITEM-C", "quantity": 1, "price": 99.99},
    ],
    "shipping_address": {
        "line1": "456 Long St",
        "city": "Johannesburg",
        "postal_code": "2000",
        "country": "ZA"
    }
}

# Minimum valid order — single item, quantity 1, lowest realistic price
# Tests that the system accepts the smallest possible valid order
VALID_ORDER_SINGLE_ITEM = {
    "customer_id": "CUST-003",
    "items": [{"sku": "ITEM-Z", "quantity": 1, "price": 9.99}],
    "shipping_address": {
        "line1": "1 Beach Rd",
        "city": "Durban",
        "postal_code": "4001",
        "country": "ZA"
    }
}


# ─────────────────────────────────────────────
# Missing required fields — expect 400 Bad Request
# ─────────────────────────────────────────────

# customer_id removed — verifies the API rejects orders with no customer
MISSING_CUSTOMER_ID = {
    "items": [{"sku": "ITEM-A", "quantity": 1, "price": 10.00}],
    "shipping_address": {"line1": "123 St", "city": "CT", "postal_code": "8001", "country": "ZA"}
}

# items removed — verifies the API rejects orders with no line items
MISSING_ITEMS = {
    "customer_id": "CUST-001",
    "shipping_address": {"line1": "123 St", "city": "CT", "postal_code": "8001", "country": "ZA"}
}

# shipping_address removed — verifies the API rejects orders with no delivery address
MISSING_SHIPPING_ADDRESS = {
    "customer_id": "CUST-001",
    "items": [{"sku": "ITEM-A", "quantity": 1, "price": 10.00}]
}

# items present but empty — an empty list is semantically wrong even if technically valid JSON
EMPTY_ITEMS_LIST = {
    "customer_id": "CUST-001",
    "items": [],
    "shipping_address": {"line1": "123 St", "city": "CT", "postal_code": "8001", "country": "ZA"}
}


# ─────────────────────────────────────────────
# Invalid field values — expect 422 Unprocessable Entity
# ─────────────────────────────────────────────
# 422 = body is valid JSON but values are semantically incorrect

# quantity: 0 — an order for zero units makes no business sense
ZERO_QUANTITY = {
    "customer_id": "CUST-001",
    "items": [{"sku": "ITEM-A", "quantity": 0, "price": 10.00}],
    "shipping_address": {"line1": "123 St", "city": "CT", "postal_code": "8001", "country": "ZA"}
}

# price: negative — a negative price would mean the customer is owed money, not valid
NEGATIVE_PRICE = {
    "customer_id": "CUST-001",
    "items": [{"sku": "ITEM-A", "quantity": 1, "price": -5.00}],
    "shipping_address": {"line1": "123 St", "city": "CT", "postal_code": "8001", "country": "ZA"}
}


# ─────────────────────────────────────────────
# Status values for update tests
# ─────────────────────────────────────────────

# All valid non-PENDING statuses — used in parametrized happy path tests
# PENDING is excluded because newly created orders start as PENDING
VALID_STATUSES = ["CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"]

# Invalid status values — used to verify the API rejects unknown statuses
# Covers: wrong word, completely wrong, numeric string
INVALID_STATUSES = ["DISPATCHED", "UNKNOWN", "123"]
