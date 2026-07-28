from pq_sdk.client import PQClient


def get_client_from_django_settings():
    """Build a PQClient from Django settings.

    Add to your settings.py:
        PQ_SDK = {
            "api_key": "your_key",
            "base_url": "http://localhost:8000",
            "environment": "production",
        }
    """
    from django.conf import settings
    cfg = getattr(settings, "PQ_SDK", {})
    return PQClient(
        api_key=cfg.get("api_key", ""),
        base_url=cfg.get("base_url", "http://localhost:8000"),
        timeout=cfg.get("timeout", 5),
        async_send=cfg.get("async_send", True),
    )


class DjangoMiddleware:
    """Django middleware that captures 500 errors automatically.

    Add to MIDDLEWARE in settings.py:
        "pq_sdk.integrations.django.DjangoMiddleware",

    Settings (optional):
        PQ_SDK = {
            "api_key": "your_key",
            "base_url": "http://localhost:8000",
            "environment": "production",
        }
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.client = get_client_from_django_settings()

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code >= 500:
            self.client.capture_error(
                message=f"{request.method} {request.path} returned {response.status_code}",
                error_type="ServerError",
                environment=getattr(self.client, "_environment", "production"),
                page=str(request.build_absolute_uri()),
                extra={
                    "status_code": response.status_code,
                    "method": request.method,
                    "path": request.path,
                },
            )
        return response

    def process_exception(self, request, exception):
        self.client.capture_exception(
            environment=getattr(self.client, "_environment", "production"),
            page=str(request.build_absolute_uri()),
            extra={
                "method": request.method,
                "path": request.path,
            },
        )
        return None
