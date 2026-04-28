"""
ResponseValidator — Chainable Assertion Helper
===============================================
Responsibility:
    Provide a readable, reusable interface for asserting API response
    properties without duplicating assertion logic across test files.

Why chainable assertions instead of raw asserts?
    Without this class, a typical test would look like:

        assert response.status_code == 201
        body = response.json()
        assert "order_id" in body
        assert body["order_id"] != ""
        assert "application/json" in response.headers["Content-Type"]

    With ResponseValidator, the same test becomes:

        ResponseValidator(response)
            .status_is(201)
            .has_field("order_id")
            .field_not_empty("order_id")
            .content_type_is_json()

    Benefits:
    - Reads like a specification — immediately clear what is being verified
    - Failure messages are descriptive — tells you exactly what went wrong
    - DRY — assertion logic defined once, reused everywhere
    - Chainable — multiple checks compose naturally on one expression
"""

from requests import Response


class ResponseValidator:
    """
    Wraps an HTTP response and exposes chainable assertion methods.

    Each method asserts a condition and returns self, allowing
    multiple assertions to be chained in a single readable expression.
    """

    def __init__(self, response: Response):
        """
        Initialise with an HTTP response object.
        Parse the JSON body immediately so it's available to all methods.
        """
        self.response = response
        # Parse body once upfront — avoids repeated JSON parsing per assertion
        self.body = self._parse_body()

    def _parse_body(self) -> dict:
        """
        Attempt to parse the response body as JSON.
        Returns an empty dict if the body is not valid JSON
        (e.g. empty responses, plain text errors).
        """
        try:
            return self.response.json()
        except Exception:
            return {}

    def status_is(self, expected: int) -> "ResponseValidator":
        """
        Assert that the HTTP status code matches the expected value.

        Includes the response body in the failure message — this is
        critical for debugging because the body often contains the
        error detail that explains why the status was wrong.
        """
        actual = self.response.status_code
        assert actual == expected, (
            f"Expected HTTP {expected}, got {actual}.\n"
            f"Response body: {self.response.text[:300]}"
        )
        return self

    def has_field(self, field: str) -> "ResponseValidator":
        """
        Assert that a field exists in the response body.

        Lists all actual keys in the failure message so the cause
        is immediately obvious without needing to re-run the test.
        """
        assert field in self.body, (
            f"Expected field '{field}' in response body.\n"
            f"Actual keys: {list(self.body.keys())}"
        )
        return self

    def field_equals(self, field: str, expected) -> "ResponseValidator":
        """
        Assert that a specific field has the expected value.
        Calls has_field first to give a clearer error if the field is missing.
        """
        self.has_field(field)
        actual = self.body[field]
        assert actual == expected, (
            f"Expected '{field}' = {expected!r}, got {actual!r}"
        )
        return self

    def field_not_empty(self, field: str) -> "ResponseValidator":
        """
        Assert that a field exists and is not None, empty string, or falsy.
        Useful for IDs and generated values where content matters but exact
        value is unknown at test design time.
        """
        self.has_field(field)
        assert self.body[field], (
            f"Expected '{field}' to be non-empty, got: {self.body[field]!r}"
        )
        return self

    def has_fields(self, *fields: str) -> "ResponseValidator":
        """
        Assert that multiple fields all exist in the response body.
        Delegates to has_field so each missing field is reported clearly.
        """
        for field in fields:
            self.has_field(field)
        return self

    def content_type_is_json(self) -> "ResponseValidator":
        """
        Assert that the response Content-Type header indicates JSON.
        Verifies the API is returning properly typed responses, not
        accidentally returning HTML error pages or plain text.
        """
        ct = self.response.headers.get("Content-Type", "")
        assert "application/json" in ct, (
            f"Expected JSON Content-Type, got: {ct}"
        )
        return self

    def error_message_contains(self, substring: str) -> "ResponseValidator":
        """
        Assert that the error or message field contains a specific substring.

        Used in authentication tests to verify not just that a 401 is
        returned, but that the error message is meaningful — e.g. that
        an expired token returns 'expired' in the message, not a generic error.

        Checks both 'error' and 'message' keys to handle different API conventions.
        """
        message = (
            self.body.get("error")
            or self.body.get("message")
            or str(self.body)
        )
        assert substring.lower() in message.lower(), (
            f"Expected error containing '{substring}'.\n"
            f"Actual message: {message}"
        )
        return self
