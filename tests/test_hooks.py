import sys
import threading
from unittest.mock import MagicMock, patch

from pq_sdk.hooks import auto_capture, capture_exceptions, install_hook
from pq_sdk.client import PQClient


class TestCaptureExceptions:
    def test_captures_and_raises(self):
        client = PQClient(api_key="k", base_url="http://localhost", async_send=False)

        with patch.object(client, "capture_exception") as mock_capture:
            try:
                with capture_exceptions(client):
                    raise ValueError("boom")
            except ValueError:
                pass
            mock_capture.assert_called_once()

    def test_no_exception_no_capture(self):
        client = PQClient(api_key="k", base_url="http://localhost", async_send=False)

        with patch.object(client, "capture_exception") as mock_capture:
            with capture_exceptions(client):
                pass
            mock_capture.assert_not_called()


class TestAutoCapture:
    def test_captures_and_raises(self):
        client = PQClient(api_key="k", base_url="http://localhost", async_send=False)

        @auto_capture(client)
        def failing():
            raise RuntimeError("oops")

        with patch.object(client, "capture_exception") as mock_capture:
            try:
                failing()
            except RuntimeError:
                pass
            mock_capture.assert_called_once()

    def test_preserves_function_name(self):
        client = PQClient(api_key="k", base_url="http://localhost", async_send=False)

        @auto_capture(client)
        def my_func():
            pass

        assert my_func.__name__ == "my_func"


class TestInstallHook:
    def test_excepthook_captures_unhandled(self):
        client = PQClient(api_key="k", base_url="http://localhost", async_send=False)
        original = sys.excepthook

        with patch.object(client, "capture_error") as mock_capture:
            install_hook(client)
            # sys.excepthook is only called for truly unhandled exceptions,
            # so call the installed hook directly to verify it works.
            exc_type = TypeError
            exc_value = TypeError("test main")
            exc_tb = None
            sys.excepthook(exc_type, exc_value, exc_tb)
            mock_capture.assert_called_once()
            call_kwargs = mock_capture.call_args
            assert call_kwargs[1]["error_type"] == "TypeError"
            assert "test main" in call_kwargs[1]["message"]
            sys.excepthook = original

    def test_thread_excepthook_captures_thread_exception(self):
        if not hasattr(threading, "excepthook"):
            return  # Python < 3.8

        client = PQClient(api_key="k", base_url="http://localhost", async_send=False)
        original = threading.excepthook

        with patch.object(client, "capture_error") as mock_capture:
            install_hook(client)

            def bad_thread():
                raise RuntimeError("thread boom")

            t = threading.Thread(target=bad_thread, name="test-worker")
            t.start()
            t.join()

            # Hook should have captured the thread exception
            mock_capture.assert_called_once()
            call_kwargs = mock_capture.call_args
            assert call_kwargs[1]["error_type"] == "RuntimeError"
            assert "thread boom" in call_kwargs[1]["message"]
            assert call_kwargs[1]["extra"]["thread_name"] == "test-worker"

            threading.excepthook = original

    def test_install_returns_none(self):
        """install_hook should not raise."""
        client = PQClient(api_key="k", base_url="http://localhost", async_send=False)
        original = sys.excepthook
        result = install_hook(client)
        assert result is None
        sys.excepthook = original
