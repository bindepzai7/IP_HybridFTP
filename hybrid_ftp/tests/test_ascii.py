"""
Unit tests for ASCII (TYPE A) line-ending translation (common/mode.AsciiCodec).
"""
import os

import pytest

from common.mode import AsciiCodec


@pytest.mark.parametrize(
    "raw",
    [
        b"a\nb\nc",       # Unix LF
        b"a\r\nb\r\nc",   # Windows CRLF
        b"a\rb\rc",       # old-Mac CR
        b"a\nb\r\nc\rd",  # mixed
    ],
)
def test_to_network_normalizes_to_crlf(raw):
    """Any newline style becomes canonical CRLF on the wire."""
    out = AsciiCodec.to_network(raw)
    assert b"\r\n" in out
    # No lone LF or lone CR remain.
    assert out.replace(b"\r\n", b"") == raw.replace(b"\r", b"").replace(b"\n", b"")


def test_to_local_uses_os_linesep():
    """Wire CRLF is converted to this host's local newline."""
    out = AsciiCodec.to_local(b"a\r\nb\r\nc")
    assert out == ("a" + os.linesep + "b" + os.linesep + "c").encode()


def test_roundtrip_is_idempotent_for_local_text():
    """A file already using local newlines survives to_network -> to_local."""
    original = ("one" + os.linesep + "two" + os.linesep).encode()
    assert AsciiCodec.to_local(AsciiCodec.to_network(original)) == original


def test_no_newlines_unchanged():
    assert AsciiCodec.to_network(b"plain text") == b"plain text"
    assert AsciiCodec.to_local(b"plain text") == b"plain text"
