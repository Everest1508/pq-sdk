import traceback

from flask import Flask, g, request

from pq_sdk.client import PQClient


class FlaskIntegration:
    """Flask integration that captures 500 errors automatically.

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

        @app.errorhandler(500)
        def handle_500(error):
            self.client.capture_error(
                message=f"{request.method} {request.path} returned 500",
                error_type="ServerError",
                page=str(request.url),
                extra={"status_code": 500},
            )
            return "Internal Server Error", 500

        @app.after_request
        def after_request(response):
            if response.status_code >= 500:
                self.client.capture_error(
                    message=f"{request.method} {request.path} returned {response.status_code}",
                    error_type="ServerError",
                    page=str(request.url),
                    extra={"status_code": response.status_code},
                )
            return response

        @app.teardown_request
        def teardown_request(exc):
            if exc is not None:
                self.client.capture_exception(
                    page=str(request.url),
                    extra={"method": request.method, "path": request.path},
                )
