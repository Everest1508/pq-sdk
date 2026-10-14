# PQ SDK

Python SDK for the PQ Platform — error tracking, feedback, and ticketing.

Zero dependencies. Works with Django, FastAPI, Flask, or any Python app.

## Install

```bash
pip install pq-befu

# Or with framework extras
pip install "pq-befu[django]"
pip install "pq-befu[fastapi]"
pip install "pq-befu[flask]"
```

## Quick Start

```python
from pq_sdk import PQClient

pq = PQClient(
    api_key="your_api_key",
    base_url="http://localhost:8000",
)

# Report an error
pq.capture_error(message="Something broke", error_type="ValueError")

# Report a caught exception
try:
    1 / 0
except Exception:
    pq.capture_exception()

# Submit feedback
pq.send_feedback(rating=5, comment="Great product!")

# Create a ticket
pq.create_ticket(title="Bug report", description="Login fails on mobile", ticket_type="bug")
```

## Auto-Capture

### Context Manager

```python
from pq_sdk.hooks import capture_exceptions

with capture_exceptions(pq, environment="production"):
    do_something_risky()  # exceptions auto-reported
```

### Decorator

```python
from pq_sdk.hooks import auto_capture

@auto_capture(pq, environment="production")
def my_view(request):
    ...
```

### Global Exception Hook

```python
from pq_sdk.hooks import install_hook

pq = PQClient(api_key="...", base_url="...")
install_hook(pq)  # unhandled exceptions auto-reported
```

## Framework Integrations

### Django

Add to `settings.py`:

```python
INSTALLED_APPS = [...]
MIDDLEWARE = [
    "pq_sdk.integrations.django.DjangoMiddleware",  # add this
    ...
]

PQ_SDK = {
    "api_key": "your_api_key",
    "base_url": "http://localhost:8000",
    "environment": "production",
}
```

### FastAPI

```python
from fastapi import FastAPI
from pq_sdk import PQClient
from pq_sdk.integrations.fastapi import FastAPIMiddleware

app = FastAPI()
pq = PQClient(api_key="your_key", base_url="http://localhost:8000")
app.add_middleware(FastAPIMiddleware, client=pq)
```

### Flask

```python
from flask import Flask
from pq_sdk import PQClient
from pq_sdk.integrations.flask import FlaskIntegration

app = Flask(__name__)
pq = PQClient(api_key="your_key", base_url="http://localhost:8000")
FlaskIntegration(app, pq)
```

## Configuration

| Parameter     | Default                      | Description                          |
|---------------|------------------------------|--------------------------------------|
| `api_key`     | (required)                   | API key from your product settings   |
| `base_url`    | `http://localhost:8000`       | Your PQ Platform URL                 |
| `timeout`     | `5`                          | HTTP timeout in seconds              |
| `async_send`  | `True`                       | Send reports in background threads   |

## Development

```bash
cd pq_sdk
pip install -e ".[dev]"
pytest
```
