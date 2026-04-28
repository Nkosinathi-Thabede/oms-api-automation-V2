# OMS API Automation Framework — Version 2

API automation framework for an Order Management System (OMS).

Version 2 improves on the original submission with:
- Comprehensive inline documentation throughout all files
- Structured commit history reflecting real development progression
- Clearer reasoning embedded directly in the code

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.12 | Core language |
| pytest | Test runner |
| requests | HTTP client |
| Flask | Local mock OMS API server |
| PyJWT | JWT token generation |
| pytest-html | HTML report generation |
| GitHub Actions | CI/CD pipeline |

---

## Project Structure

```
oms-api-automation-v2/
├── framework/
│   ├── auth/token_manager.py           # JWT generation, caching, expired token helper
│   ├── client/api_client.py            # Reusable HTTP client with auth swap pattern
│   ├── validators/response_validator.py # Chainable assertion helpers
│   └── utils/logger.py                 # Centralised logging
├── mock_server/server.py               # Flask mock OMS API — full order lifecycle
├── tests/
│   ├── test_create_order.py            # POST /orders — 15 test cases
│   ├── test_get_order.py               # GET /orders/{id} — 11 test cases
│   └── test_update_order_status.py     # PUT /orders/{id}/status — 16 test cases
├── test_data/order_payloads.py         # All test payloads centralised
├── conftest.py                         # Shared fixtures and mock server lifecycle
├── pytest.ini                          # Pytest configuration
└── .github/workflows/ci.yml           # GitHub Actions CI pipeline
```

---

## Running Locally

```bash
git clone https://github.com/Nkosinathi-Thabede/oms-api-automation-V2.git
cd oms-api-automation-V2

python3 -m venv venv
source venv/bin/activate       # Mac/Linux
# venv\Scripts\activate        # Windows

pip install -r requirements.txt
pytest
```

Open `reports/report.html` in a browser after the run to view the full test report.

---

## Test Coverage

| Suite | Tests | Scope |
|-------|-------|-------|
| Create Order | 15 | Happy path, missing fields, invalid values, auth |
| Get Order | 11 | Happy path, not found, auth |
| Update Status | 16 | Valid transitions, invalid values, terminal states, auth |
| **Total** | **52** | |
