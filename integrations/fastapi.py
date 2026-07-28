import traceback

from starlette.middleware.base import BaseHTTPMiddleware

from pq_sdk.client import PQClient


class FastAPIMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that captures 500 errors automatically.

    Usage:
        from pq_sdk.integrations.fastapi import FastAPIMiddleware
        from pq_sdk import PQClient

        app = FastAPI()
        pq = PQClient(api_key="your_key", base_url="http://localhost:8000")
        app.add_middleware(FastAPIMiddleware, client=pq)

    Or with settings dict:
        app.add_middleware(FastAPIMiddleware, settings={
            "api_key": "your_key",
            "base_url": "http://localhost:8000",
        })
    """

    def __init__(self, app, client=None, settings=None):
        super().__init__(app)
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
            raise ValueError("Provide either 'client' or 'settings' to FastAPIMiddleware")

    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            if response.status_code >= 500:
                self.client.capture_error(
                    message=f"{request.method} {request.url.path} returned {response.status_code}",
                    error_type="ServerError",
                    page=str(request.url),
                    extra={"status_code": response.status_code},
                )
            return response
        except Exception as exc:
            self.client.capture_exception(
                page=str(request.url),
                extra={"method": request.method, "path": request.url.path},
            )
            raise
