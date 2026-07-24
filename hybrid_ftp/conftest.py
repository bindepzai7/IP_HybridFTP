"""
Shared pytest configuration and fixtures.

Placed at hybrid_ftp/ so that `common`, `server`, and `client` resolve as
top-level packages -- the same import model the app uses when run from inside
this directory (e.g. `python -m server`).
"""
import os
import socket
import sys
import threading
import time

import pytest

# Make hybrid_ftp/ importable as the package root, matching how the app runs.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# --- End-to-end fixtures (used by the FTP command tests) ---

TEST_USER = "testuser"
TEST_PASS = "testpass"


@pytest.fixture(scope="session")
def _test_account():
    """Ensure a known account exists in the server's auth store."""
    from server.auth import Authenticator

    Authenticator().add_user(TEST_USER, TEST_PASS)  # no-op if already present
    return (TEST_USER, TEST_PASS)


@pytest.fixture
def server(_test_account):
    """Start an FTPServer on an ephemeral loopback port in a background thread.

    Yields (host, port). Tears the server down by closing its listen socket,
    which unblocks accept() and ends the thread.
    """
    from server.server import FTPServer

    srv = FTPServer(host="127.0.0.1", port=0)
    thread = threading.Thread(target=srv.start, daemon=True)
    thread.start()

    # Wait for start() to bind the socket, then read the real port.
    port = 0
    for _ in range(200):
        try:
            port = srv.sock.getsockname()[1]
        except OSError:
            port = 0
        if port:
            break
        time.sleep(0.01)
    assert port, "server did not bind to a port"

    yield ("127.0.0.1", port)

    srv.stop()


@pytest.fixture
def client(server):
    """A connected, welcomed FTPClient pointed at the test server."""
    from client.client import FTPClient

    host, port = server
    c = FTPClient()
    c.connect(host, port)
    c.control.read_line()  # consume the 220 welcome banner
    yield c
    try:
        c.disconnect()
    except Exception:
        pass


@pytest.fixture
def logged_in_client(client):
    """An FTPClient that has completed USER/PASS authentication."""
    client._send_cmd(f"USER {TEST_USER}")
    client._send_cmd(f"PASS {TEST_PASS}")
    return client
