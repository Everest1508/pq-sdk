import atexit
import json
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.request import Request, urlopen


class PQClient:
    """Client for the PQ Platform ingestion API.

    Usage:
        from pq_sdk import PQClient

        pq = PQClient(
            api_key="your_api_key_here",
            base_url="http://localhost:8000",
        )

        pq.capture_error(message="Something broke", error_type="ValueError")
        pq.send_feedback(rating=5, comment="Great product!")
        pq.create_ticket(title="Bug report", description="Login fails on mobile", ticket_type="bug")

        # Ensure all async requests complete before exit
        pq.flush()
    """

    def __init__(self, api_key, base_url="http://localhost:8000", timeout=5, async_send=True):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.async_send = async_send
        self._executor = None
        self._futures = []
        if async_send:
            self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pq_sdk")
            atexit.register(self.flush)

    def flush(self):
        """Wait for all pending async requests to complete.

        Call this before your program exits to ensure no data is lost.
        Not needed when async_send=False (sync mode).
        """
        if self._executor:
            pending = [f for f in self._futures if not f.done()]
            if pending:
                wait(pending)

    def _post(self, endpoint, data):
        url = f"{self.base_url}/api/v1/{endpoint}"
        body = json.dumps(data).encode("utf-8")
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            resp = urlopen(req, timeout=self.timeout)
            return json.loads(resp.read().decode())
        except Exception as exc:
            print(f"[pq_sdk] {endpoint.strip('/')} failed: {exc}", file=sys.stderr)
            return None

    def _send(self, endpoint, data):
        if self._executor:
            future = self._executor.submit(self._post, endpoint, data)
            self._futures.append(future)
            return future
        else:
            return self._post(endpoint, data)

    # ── Error capture ─────────────────────────────────────────────

    def capture_error(self, message, error_type="", stacktrace="", **kwargs):
        """Report an error to the platform.

        Args:
            message: Error message (required).
            error_type: Exception class name (e.g. "ValueError").
            stacktrace: Stack trace string.
            **kwargs: Optional fields — environment, version, page,
                      user_ref, device, os, browser, request_payload, extra.
        """
        data = {
            "message": message[:1000],
            "error_type": error_type[:255],
            "stacktrace": stacktrace,
            **kwargs,
        }
        return self._send("errors/capture/", data)

    def capture_exception(self, exc_info=None, **kwargs):
        """Report a caught exception.

        Args:
            exc_info: Tuple from sys.exc_info(). Defaults to current exception.
            **kwargs: Extra fields passed to capture_error.
        """
        if exc_info is None:
            exc_info = sys.exc_info()
        exc_type, exc_value, exc_tb = exc_info
        if exc_type is None:
            return None
        stacktrace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        return self.capture_error(
            message=str(exc_value)[:1000],
            error_type=exc_type.__name__,
            stacktrace=stacktrace,
            **kwargs,
        )

    # ── Feedback ──────────────────────────────────────────────────

    def send_feedback(self, rating, comment="", user_ref="", **kwargs):
        """Submit user feedback (rating 1-5).

        Args:
            rating: Integer 1-5.
            comment: Free text comment.
            user_ref: Identifier for the user giving feedback.
            **kwargs: Optional fields — version, screenshot_url.
        """
        data = {
            "rating": rating,
            "comment": comment,
            "user_ref": user_ref,
            **kwargs,
        }
        return self._send("feedback/", data)

    # ── Tickets ───────────────────────────────────────────────────

    def create_ticket(self, title, description="", ticket_type="bug", user_ref="", **kwargs):
        """Create a support ticket.

        Args:
            title: Ticket title.
            description: Detailed description.
            ticket_type: One of "bug", "feature", "question".
            user_ref: Identifier for the user reporting.
            **kwargs: Optional fields — external_id, metadata.
        """
        data = {
            "title": title[:500],
            "description": description,
            "ticket_type": ticket_type,
            "user_ref": user_ref,
            **kwargs,
        }
        return self._send("tickets/", data)
