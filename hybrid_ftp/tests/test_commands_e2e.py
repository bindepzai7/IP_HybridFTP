"""
End-to-end FTP command tests.

These drive a real FTPClient against a real FTPServer (started per-test by the
`server` fixture in conftest.py), exercising the full stack: TCP control
channel + UDP/RDT data channel + hash verification. Passive mode is used for
all transfers.
"""
import os

import pytest

from client.client import STORAGE_DIR
from server.filesystem import ROOT_DIR


def _code(resp):
    """First token of a reply line, e.g. '230 User logged in' -> '230'."""
    return resp.split()[0] if resp else ""


# --- Authentication ---

def test_login_flow(client):
    assert _code(client._send_cmd("USER testuser")) == "331"
    assert _code(client._send_cmd("PASS testpass")) == "230"


def test_bad_password_rejected(client):
    client._send_cmd("USER testuser")
    assert _code(client._send_cmd("PASS wrongpass")) == "530"


def test_command_requires_login(client):
    assert _code(client._send_cmd("PWD")) == "530"


# --- Navigation / directory ops ---

def test_pwd_and_navigation(logged_in_client):
    c = logged_in_client
    assert _code(c._send_cmd("PWD")) == "257"
    assert _code(c._send_cmd("MKD e2e_dir")) == "257"
    assert _code(c._send_cmd("CWD e2e_dir")) == "250"
    assert "e2e_dir" in c._send_cmd("PWD")
    assert _code(c._send_cmd("CDUP")) == "250"
    assert _code(c._send_cmd("RMD e2e_dir")) == "250"


def test_noop_and_help(logged_in_client):
    assert _code(logged_in_client._send_cmd("NOOP")) == "200"
    assert _code(logged_in_client._send_cmd("HELP")) == "200"


@pytest.mark.parametrize("arg, expected", [("I", "200"), ("A", "200"), ("X", "501")])
def test_type_switch(logged_in_client, arg, expected):
    assert _code(logged_in_client._send_cmd(f"TYPE {arg}")) == expected


def test_pasv_with_arg_sends_single_reply(logged_in_client):
    """PASV takes no argument; a bad call must reply exactly once (no desync)."""
    c = logged_in_client
    assert _code(c._send_cmd("PASV extra")) == "500"
    # If a stray second reply had been queued, this would read that instead of 200.
    assert _code(c._send_cmd("NOOP")) == "200"


def test_stou_with_arg_sends_single_reply(logged_in_client):
    """STOU takes no argument; a bad call must reply once and not open data."""
    c = logged_in_client
    c._send_cmd("PASV")  # give the session a data channel so we reach the arg check
    assert _code(c._send_cmd("STOU junk")) == "501"
    assert _code(c._send_cmd("NOOP")) == "200"


# --- Transfers (data channel + hash) ---

@pytest.fixture
def sample_file():
    """Create a local file to upload; clean up all copies afterward."""
    name = "e2e_upload.txt"
    content = b"end-to-end hybrid ftp test payload\n" * 50
    local = os.path.join(STORAGE_DIR, name)
    with open(local, "wb") as f:
        f.write(content)

    yield name, content

    for p in (
        local,
        os.path.join(STORAGE_DIR, "e2e_download.txt"),
        os.path.join(ROOT_DIR, name),
        os.path.join(ROOT_DIR, "e2e_renamed.txt"),
    ):
        try:
            os.remove(p)
        except OSError:
            pass


def test_upload_download_roundtrip(logged_in_client, sample_file):
    c = logged_in_client
    name, content = sample_file

    c.set_passive_mode()
    c.stor(name, name)

    assert _code(c._send_cmd(f"SIZE {name}")) == "213"

    c.set_passive_mode()
    c.retr(name, "e2e_download.txt")

    with open(os.path.join(STORAGE_DIR, "e2e_download.txt"), "rb") as f:
        assert f.read() == content


def test_transfer_without_manual_pasv(logged_in_client, sample_file):
    """STOR/RETR auto-negotiate passive mode when no PASV/PORT was issued."""
    c = logged_in_client
    name, content = sample_file

    # Note: no c.set_passive_mode() here -- the client should default to it.
    c.stor(name, name)
    c.retr(name, "e2e_download.txt")

    with open(os.path.join(STORAGE_DIR, "e2e_download.txt"), "rb") as f:
        assert f.read() == content


def test_ascii_mode_roundtrip(logged_in_client):
    """A text file survives an ASCII-mode upload+download round-trip.

    On a single host to_local(to_network(x)) is idempotent when x already uses
    the local newline convention, so the downloaded copy equals the original.
    """
    c = logged_in_client
    c.set_type("A")
    name = "e2e_ascii.txt"
    content = ("alpha" + os.linesep + "beta" + os.linesep + "gamma").encode()
    local = os.path.join(STORAGE_DIR, name)
    with open(local, "wb") as f:
        f.write(content)

    try:
        c.stor(name, name)
        c.retr(name, "e2e_ascii_dl.txt")
        with open(os.path.join(STORAGE_DIR, "e2e_ascii_dl.txt"), "rb") as f:
            assert f.read() == content
    finally:
        for p in (local, os.path.join(STORAGE_DIR, "e2e_ascii_dl.txt"),
                  os.path.join(ROOT_DIR, name)):
            try:
                os.remove(p)
            except OSError:
                pass


def test_ascii_mode_skips_hash(logged_in_client, sample_file, capsys):
    """Hash verification is skipped in ASCII mode (bytes differ by newline)."""
    c = logged_in_client
    c.verbose_hash = True
    c.set_type("A")
    name, _ = sample_file
    c.stor(name, name)
    out = capsys.readouterr().out
    assert "MATCH" not in out


def test_verify_hash_silent_by_default(logged_in_client, sample_file, capsys):
    """Default client stays silent on a successful integrity check."""
    c = logged_in_client
    name, _ = sample_file
    c.stor(name, name)
    assert "MATCH" not in capsys.readouterr().out


def test_verify_hash_verbose_prints_match(logged_in_client, sample_file, capsys):
    """With verbose_hash on, a successful check is reported."""
    c = logged_in_client
    c.verbose_hash = True
    name, _ = sample_file
    c.stor(name, name)
    assert "SHA-256 MATCH" in capsys.readouterr().out


def test_hash_matches_after_upload(logged_in_client, sample_file):
    c = logged_in_client
    name, _ = sample_file
    c.set_passive_mode()
    c.stor(name, name)
    # verify_hash asks the server for its SHA-256 and compares to the local file
    assert c.verify_hash(name, os.path.join(STORAGE_DIR, name)) is True


def test_rename_and_delete(logged_in_client, sample_file):
    c = logged_in_client
    name, _ = sample_file
    c.set_passive_mode()
    c.stor(name, name)
    assert _code(c._send_cmd(f"RNFR {name}")) == "350"
    assert _code(c._send_cmd("RNTO e2e_renamed.txt")) == "250"
    assert _code(c._send_cmd("DELE e2e_renamed.txt")) == "250"
