from flask import Flask, request
from werkzeug.exceptions import HTTPException

from pq_sdk.client import PQClient
from pq_sdk.hooks import install_hook


class FlaskIntegration:
    """Flask integration that captures ALL unhandled exceptions automatically.

    Covers:
      - View exceptions (teardown_request with exception)
      - 500 status responses (after_request check)
      - Startup crashes (via sys.excepthook)
      - Background threads (via threading.excepthook)

    Usage:
        from pq_sdk.integrations.flask import FlaskIntegration
        from pq_sdk import PQClient

        app = Flask(__name__)
        pq = PQClient(api_key="your_key", base_url="http://localhost:8000")
        FlaskIntegration(app, pq)

    Or with config dict:
        FlaskIntegration(app, settings={
            "api_key": "your_key",
            "base_url": "http://localhost:8000",
        })
    """

    _hook_installed = False

    def __init__(self, app=None, client=None, settings=None):
        if client:
            self.client = client
        elif settings:
            self.client = PQClient(
                api_key=settings.get("api_key", ""),
                base_url=settings.get("base_url", "http://localhost:8000"),
                timeout=settings.get("timeout", 5),
                async_send=settings.get("async_send", True),
            )
        else:
            raise ValueError("Provide either 'client' or 'settings' to FlaskIntegration")

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.extensions["pq_sdk"] = self.client

        # Install sys.excepthook + threading.excepthook once
        if not FlaskIntegration._hook_installed:
            install_hook(self.client)
            FlaskIntegration._hook_installed = True

        @app.teardown_request
        def _pq_teardown(exc):
            if exc is not None and not isinstance(exc, HTTPException):
                # Only capture real exceptions, not HTTP errors (4xx/5xx are handled by Flask)
                self.client.capture_exception(
                    page=str(request.url) if request else "unknown",
                    extra={"method": request.method if request else "unknown"},
                )

        @app.after_request
        def _pq_after_request(response):
            if response.status_code >= 500:
                self.client.capture_error(
                    message=f"{request.method} {request.path} returned {response.status_code}",
                    error_type="ServerError",
                    page=str(request.url),
                    extra={"status_code": response.status_code},
                )
            return response
