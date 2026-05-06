# Solution Design & Trade-offs

## Overview

This document explains the key design decisions made in building the OMS API automation framework.

---

## Key Decisions

### 1. Python + pytest + requests
Chosen for readability, low boilerplate, and strong API testing ecosystem. `requests` maps directly to Postman concepts — same mental model, in code. `pytest` is industry-standard with native support for fixtures, parametrize, and HTML reporting.

### 2. Flask Mock Server
Tests run against a local Flask server with zero external dependencies. This means:
- No credentials, VPN, or network access required
- Fully reproducible across any environment
- Controlled test data — no shared environment pollution
- CI/CD works without secrets management

The mock server starts automatically via a `session`-scoped pytest fixture and shuts down when tests complete.

### 3. Layered Architecture

| Layer | Responsibility |
|-------|---------------|
| `APIClient` | HTTP mechanics — base URL, headers, session |
| `TokenManager` | Auth — JWT generation, caching, expiry simulation |
| `ResponseValidator` | Assertions — chainable, readable, DRY |
| `test_data/` | Payloads separated from test logic |
| `tests/` | Test intent — what and why |

Changes to auth only touch `TokenManager`. New assertions only touch `ResponseValidator`.

### 4. Chainable ResponseValidator
```python
ResponseValidator(response).status_is(201).has_field("order_id").field_not_empty("order_id")
```
Improves readability, produces clearer failure messages, and eliminates repeated assert patterns across test files.

### 5. Data-Driven Testing
`@pytest.mark.parametrize` runs multiple scenarios as individually named tests — granular pass/fail visibility without code duplication.

### 6. Session-Scoped Fixtures
`client`, `token`, and mock server are created once per test run (not per test). The `created_order` fixture is function-scoped, creating a fresh order for each test that needs one — avoiding state leakage between tests.

### 7. Terminal State Protection
The mock server enforces real business rules — `DELIVERED` and `CANCELLED` orders cannot be updated. The test suite validates these constraints explicitly.

---

## What I Would Add With More Time

1. **Contract testing (Pact)** — verify mock stays aligned with the real OMS API
2. **Performance baseline assertions** — e.g. order creation must respond within 200ms
3. **Allure reporting** — richer test history and trend analysis
4. **Environment config** — `.env` files for base URL and credentials per environment
5. **Parallel execution** — `pytest-xdist` for large suite performance
6. **Test teardown** — clean up created orders after each run for full isolation
