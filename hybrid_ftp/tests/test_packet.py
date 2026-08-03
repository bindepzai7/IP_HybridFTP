"""
Unit tests for the custom UDP packet format (common/packet.py).

Pure, socket-free: only serialization (to_bytes / from_bytes), the CRC32
checksum, and the flag helpers.
"""
import pytest

from common.packet import Packet, HEADER_SIZE, FLAG_DATA, FLAG_ACK, FLAG_FIN


def test_roundtrip_data():
    """A DATA packet survives to_bytes -> from_bytes unchanged."""
    p = Packet(seq=5, ack=0, flags=FLAG_DATA, payload=b"hello world")
    q = Packet.from_bytes(p.to_bytes())
    assert q.seq == 5
    assert q.flags == FLAG_DATA
    assert q.payload == b"hello world"
    assert q.length == len(b"hello world")


def test_roundtrip_empty_payload():
    """Header-only packets (e.g. ACKs) round-trip with no payload."""
    p = Packet(seq=0, ack=7, flags=FLAG_ACK)
    q = Packet.from_bytes(p.to_bytes())
    assert q.ack == 7
    assert q.is_ack
    assert q.payload == b""


@pytest.mark.parametrize(
    "flags, prop",
    [(FLAG_DATA, "is_data"), (FLAG_ACK, "is_ack"), (FLAG_FIN, "is_fin")],
)
def test_flag_properties(flags, prop):
    assert getattr(Packet(flags=flags), prop) is True


def test_data_is_not_ack():
    assert Packet(flags=FLAG_DATA).is_ack is False


@pytest.mark.parametrize("index", [0, HEADER_SIZE, -1])
def test_corruption_detected(index):
    """Flipping any byte (header or payload) must fail the checksum."""
    raw = bytearray(Packet(seq=1, flags=FLAG_DATA, payload=b"abcdef").to_bytes())
    raw[index] ^= 0xFF
    with pytest.raises(ValueError):
        Packet.from_bytes(bytes(raw))


def test_truncated_header_rejected():
    with pytest.raises(ValueError):
        Packet.from_bytes(b"\x00\x01")  # shorter than a full header


def test_length_mismatch_rejected():
    """Trailing bytes make declared length != actual length."""
    raw = Packet(seq=1, flags=FLAG_DATA, payload=b"abcdef").to_bytes()
    with pytest.raises(ValueError):
        Packet.from_bytes(raw + b"extra")


def test_header_size_is_15_bytes():
    """seq(4) + ack(4) + flags(1) + length(2) + csum(4) = 15 bytes."""
    assert HEADER_SIZE == 15
