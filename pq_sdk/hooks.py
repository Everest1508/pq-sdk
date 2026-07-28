import functools
import os
import signal
import sys
import threading
import traceback
from contextlib import contextmanager


@contextmanager
def capture_exceptions(client, **defaults):
    """Context manager that auto-reports exceptions.

    Usage:
        with capture_exceptions(pq, environment="production"):
            do_something_risky()
    """
    try:
        yield
    except Exception:
        client.capture_exception(**defaults)
        raise


def auto_capture(client, **defaults):
    """Decorator that auto-reports exceptions from a function.

    Usage:
        @auto_capture(pq, environment="production")
        def my_view(request):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                client.capture_exception(**defaults)
                raise
        return wrapper
    return decorator


def install_hook(client, **defaults):
    """Install hooks that capture ALL unhandled exceptions.

    Covers three scenarios:
      1. sys.excepthook — main thread unhandled exceptions
      2. threading.excepthook — exceptions in background threads
      3. signal handlers — fatal signals (SIGSEGV, SIGABRT, etc.)

    Call once at app startup. Sends to PQ Platform, then falls through
    to the default handler (prints traceback, re-raises, etc.).

    Usage:
        pq = PQClient(api_key="...", base_url="...")
        install_hook(pq, environment="production")
    """

    # ── 1. sys.excepthook (main thread) ───────────────────────────
    original_excepthook = sys.excepthook

    def pq_excepthook(exc_type, exc_value, exc_tb):
        if exc_type is not None:
            stacktrace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            client.capture_error(
                message=str(exc_value)[:1000],
                error_type=exc_type.__name__,
                stacktrace=stacktrace,
                **defaults,
            )
        return original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = pq_excepthook

    # ── 2. threading.excepthook (background threads) ──────────────
    # Python 3.8+ only
    if hasattr(threading, "excepthook"):
        original_thread_hook = threading.excepthook

        def pq_thread_hook(args):
            if args.exc_type is not None:
                stacktrace = "".join(
                    traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
                )
                client.capture_error(
                    message=str(args.exc_value)[:1000],
                    error_type=args.exc_type.__name__,
                    stacktrace=stacktrace,
                    extra={
                        "thread_name": args.thread.name if args.thread else "unknown",
                        "thread_ident": args.thread.ident if args.thread else None,
                    },
                    **defaults,
                )
            return original_thread_hook(args)

        threading.excepthook = pq_thread_hook

    # ── 3. Fatal signal handler ───────────────────────────────────
    # Best-effort: send one last report before the process dies.
    # Only works on the main thread, and only for synchronous signals.
    _original_sigsegv = signal.getsignal(signal.SIGSEGV)
    _original_sigabrt = signal.getsignal(signal.SIGABRT)

    def _fatal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        client.capture_error(
            message=f"Fatal signal: {sig_name} (process exiting)",
            error_type="FatalSignal",
            stacktrace=traceback.format_stack(frame) if frame else "",
            extra={"signal": sig_name, "pid": os.getpid()},
            **defaults,
        )
        # Re-raise with original handler so default behavior (core dump / abort) still happens
        if signum == signal.SIGSEGV:
            signal.signal(signal.SIGSEGV, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGSEGV)
        elif signum == signal.SIGABRT:
            signal.signal(signal.SIGABRT, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGABRT)

    try:
        signal.signal(signal.SIGSEGV, _fatal_handler)
    except (OSError, ValueError):
        pass  # can't set on non-main thread or Windows
    try:
        signal.signal(signal.SIGABRT, _fatal_handler)
    except (OSError, ValueError):
        pass
