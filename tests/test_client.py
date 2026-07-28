import json
from unittest.mock import MagicMock, patch

from pq_sdk.client import PQClient


class TestPQClient:
    def setup_method(self):
        self.client = PQClient(
            api_key="test_key_123",
            base_url="http://localhost:8000",
            async_send=False,
        )

    @patch("pq_sdk.client.urlopen")
    def test_capture_error(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"id": 1}).encode()
        mock_urlopen.return_value = mock_resp

        result = self.client.capture_error(
            message="Test error",
            error_type="ValueError",
            stacktrace="line 1",
        )

        assert result == {"id": 1}
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.full_url == "http://localhost:8000/api/v1/errors/capture/"
        assert req.get_header("Authorization") == "Bearer test_key_123"
        body = json.loads(req.data.decode())
        assert body["message"] == "Test error"
        assert body["error_type"] == "ValueError"

    @patch("pq_sdk.client.urlopen")
    def test_capture_exception(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"id": 2}).encode()
        mock_urlopen.return_value = mock_resp

        try:
            raise ValueError("bad value")
        except ValueError:
            result = self.client.capture_exception()

        assert result == {"id": 2}
        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        assert body["message"] == "bad value"
        assert body["error_type"] == "ValueError"
        assert "Traceback" in body["stacktrace"]

    @patch("pq_sdk.client.urlopen")
    def test_send_feedback(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"id": 3}).encode()
        mock_urlopen.return_value = mock_resp

        result = self.client.send_feedback(rating=5, comment="Great!", user_ref="u1")

        assert result == {"id": 3}
        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        assert body["rating"] == 5
        assert body["comment"] == "Great!"
        assert body["user_ref"] == "u1"

    @patch("pq_sdk.client.urlopen")
    def test_create_ticket(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"id": 4}).encode()
        mock_urlopen.return_value = mock_resp

        result = self.client.create_ticket(
            title="Bug report",
            description="Login fails",
            ticket_type="bug",
        )

        assert result == {"id": 4}
        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        assert body["title"] == "Bug report"
        assert body["ticket_type"] == "bug"

    @patch("pq_sdk.client.urlopen", side_effect=Exception("network error"))
    def test_capture_error_returns_none_on_failure(self, mock_urlopen):
        result = self.client.capture_error(message="test")
        assert result is None

    def test_async_send(self):
        client = PQClient(api_key="key", base_url="http://localhost", async_send=True)
        assert client._executor is not None
        client._shutdown()
