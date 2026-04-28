"""
Mock OMS API Server
====================
Responsibility:
    Simulate the Order Management System API locally so the test suite
    has zero external dependencies.

Why a real Flask server instead of mocking functions in memory?
    Function-level mocking (e.g. unittest.mock) patches Python objects
    but never exercises the HTTP layer. That means:
    - Missing or malformed headers go undetected
    - Wrong Content-Type responses go undetected
    - Auth token validation is bypassed entirely

    A real running server receives actual HTTP requests over the network,
    which is much closer to production behaviour. Every HTTP-level issue
    — wrong headers, missing auth, malformed JSON — will be caught.

Auto-start:
    This server is started automatically by the session-scoped
    mock_server fixture in conftest.py. Tests never need to manage it.

Business rules enforced:
    - All endpoints require a valid JWT token (401 if missing/invalid/expired)
    - Order creation validates required fields, item structure, and values
    - Status updates only accept defined valid statuses
    - DELIVERED and CANCELLED orders cannot have their status changed
      (these are terminal states — real OMS systems enforce this to
       prevent data corruption in order history)
"""

from flask import Flask, request, jsonify
import uuid
import time
import jwt

app = Flask(__name__)

# Must match the secret in token_manager.py — used to verify incoming tokens
SECRET = "oms-test-secret-key"
ALGORITHM = "HS256"

# The full set of valid order statuses in the OMS lifecycle
# Order flows: PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED
# At any point before DELIVERED, an order can also move to: CANCELLED
VALID_STATUSES = ["PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]

# In-memory store — resets on each test run, which keeps tests isolated
# In a real system this would be a database
orders: dict = {}


# ─────────────────────────────────────────────
# Auth helper
# ─────────────────────────────────────────────

def verify_token(req) -> tuple:
    """
    Validate the JWT Bearer token from the Authorization header.

    Returns:
        (True, "")           if the token is valid
        (False, error_msg)   if missing, expired, or invalid

    Why check here instead of a decorator?
    Flask decorators would add complexity for this scope. Calling
    verify_token() explicitly at the top of each route makes the
    auth check visible and easy to follow.
    """
    auth = req.headers.get("Authorization", "")

    # Token must be in "Bearer <token>" format
    if not auth.startswith("Bearer "):
        return False, "Missing or malformed Authorization header"

    token = auth.split(" ", 1)[1]
    try:
        jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return True, ""
    except jwt.ExpiredSignatureError:
        # Specific message used by test: error_message_contains("expired")
        return False, "Token has expired"
    except jwt.InvalidTokenError as e:
        return False, str(e)


# ─────────────────────────────────────────────
# Health endpoint
# ─────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """
    Simple liveness check used by conftest.py to confirm the server
    is ready before tests start. No auth required.
    """
    return jsonify({"status": "ok"}), 200


# ─────────────────────────────────────────────
# POST /orders — Create a new order
# ─────────────────────────────────────────────

@app.route("/orders", methods=["POST"])
def create_order():
    """
    Create a new order in the OMS.

    Validation sequence (order matters — most fundamental checks first):
    1. Auth token must be valid
    2. Request body must be present and valid JSON
    3. Required fields must all be present
    4. Items list must be non-empty
    5. Each item must have sku, quantity, and price
    6. Quantity must be > 0 (zero-quantity orders make no business sense)
    7. Price must be >= 0 (negative prices are invalid)

    On success: returns the full order object with a generated ID and
    calculated total, status set to PENDING.
    """
    # Step 1 — Auth check
    ok, err = verify_token(request)
    if not ok:
        return jsonify({"error": err}), 401

    # Step 2 — Body presence
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body is required"}), 400

    # Step 3 — Required fields
    missing = [f for f in ["customer_id", "items", "shipping_address"] if f not in body]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    # Step 4 — Items list must not be empty
    if not isinstance(body["items"], list) or len(body["items"]) == 0:
        return jsonify({"error": "items must be a non-empty list"}), 400

    # Step 5–7 — Validate each item's structure and values
    for item in body["items"]:
        if "sku" not in item or "quantity" not in item or "price" not in item:
            return jsonify({"error": "Each item requires sku, quantity, and price"}), 400
        if item["quantity"] <= 0:
            # 422 Unprocessable Entity — body is valid JSON but values are semantically wrong
            return jsonify({"error": "Item quantity must be greater than zero"}), 422
        if item["price"] < 0:
            return jsonify({"error": "Item price cannot be negative"}), 422

    # Build the order — generate a unique ID and calculate the total
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    total = sum(i["quantity"] * i["price"] for i in body["items"])

    order = {
        "order_id": order_id,
        "customer_id": body["customer_id"],
        "items": body["items"],
        "shipping_address": body["shipping_address"],
        "status": "PENDING",          # All orders start as PENDING
        "total": round(total, 2),     # Round to 2dp for currency precision
        "created_at": int(time.time())
    }

    orders[order_id] = order
    return jsonify(order), 201


# ─────────────────────────────────────────────
# GET /orders/{order_id} — Retrieve an order
# ─────────────────────────────────────────────

@app.route("/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    """
    Retrieve a single order by its ID.

    Returns 404 if the order does not exist — not a 400 or 500.
    404 is the correct HTTP semantic for "resource not found".
    """
    ok, err = verify_token(request)
    if not ok:
        return jsonify({"error": err}), 401

    order = orders.get(order_id)
    if not order:
        return jsonify({"error": f"Order {order_id} not found"}), 404

    return jsonify(order), 200


# ─────────────────────────────────────────────
# PUT /orders/{order_id}/status — Update order status
# ─────────────────────────────────────────────

@app.route("/orders/<order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    """
    Update the status of an existing order.

    Business rules enforced:
    - Status must be one of the defined VALID_STATUSES
    - DELIVERED is a terminal state — no further updates allowed
      (prevents reverting a completed order, which would corrupt history)
    - CANCELLED is a terminal state — same reason

    Why 409 Conflict for terminal state violations?
    409 indicates the request is valid but conflicts with the current
    state of the resource — which is exactly what's happening here.
    The order exists and the status is valid, but the transition is
    not permitted given the current state.
    """
    ok, err = verify_token(request)
    if not ok:
        return jsonify({"error": err}), 401

    order = orders.get(order_id)
    if not order:
        return jsonify({"error": f"Order {order_id} not found"}), 404

    body = request.get_json(silent=True)
    if not body or "status" not in body:
        return jsonify({"error": "Field 'status' is required"}), 400

    new_status = body["status"].upper()

    # Validate against the allowed status list
    if new_status not in VALID_STATUSES:
        return jsonify({
            "error": f"Invalid status '{new_status}'. Valid values: {VALID_STATUSES}"
        }), 422

    # Enforce terminal state protection
    if order["status"] == "DELIVERED" and new_status != "DELIVERED":
        return jsonify({"error": "Cannot update status of a delivered order"}), 409

    if order["status"] == "CANCELLED":
        return jsonify({"error": "Cannot update status of a cancelled order"}), 409

    # Apply the update
    order["status"] = new_status
    orders[order_id] = order
    return jsonify(order), 200


if __name__ == "__main__":
    # debug=False is intentional — debug mode reloads the server on file changes
    # which would interfere with the pytest session fixture lifecycle
    app.run(port=5050, debug=False)
