"""
UDP data channel with stop-and-wait reliability.

Packet layout (network byte order):
  seq_num   : uint32  - sequence number (0/1 alternating per chunk)
  flags     : uint8   - DATA=0, ACK=1, FIN=2
  length    : uint16  - payload length
  checksum  : uint32  - zlib CRC32 of payload
  payload   : bytes   - up to MAX_PAYLOAD bytes
"""

import socket
import struct
import zlib

HEADER_FMT = "!I B H I"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

FLAG_DATA = 0
FLAG_ACK = 1
FLAG_FIN = 2

MAX_PAYLOAD = 1024
DEFAULT_TIMEOUT = 1.0
MAX_RETRIES = 10


def _pack_packet(seq: int, flags: int, payload: bytes) -> bytes:
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    header = struct.pack(HEADER_FMT, seq, flags, len(payload), checksum)
    return header + payload


def _unpack_packet(data: bytes):
    if len(data) < HEADER_SIZE:
        return None

    seq, flags, length, checksum = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
    payload = data[HEADER_SIZE : HEADER_SIZE + length]

    if len(payload) != length:
        return None

    if (zlib.crc32(payload) & 0xFFFFFFFF) != checksum:
        return None

    return seq, flags, payload


def _send_ack(sock: socket.socket, peer_addr, seq: int) -> None:
    packet = _pack_packet(seq, FLAG_ACK, b"")
    sock.sendto(packet, peer_addr)


def send_bytes(sock: socket.socket, data: bytes, peer_addr, timeout: float = DEFAULT_TIMEOUT) -> None:
    sock.settimeout(timeout)
    seq = 0
    offset = 0

    while offset < len(data):
        chunk = data[offset : offset + MAX_PAYLOAD]
        packet = _pack_packet(seq, FLAG_DATA, chunk)

        for _ in range(MAX_RETRIES):
            sock.sendto(packet, peer_addr)
            try:
                raw, _ = sock.recvfrom(HEADER_SIZE + MAX_PAYLOAD)
                parsed = _unpack_packet(raw)
                if parsed and parsed[0] == seq and parsed[1] == FLAG_ACK:
                    break
            except socket.timeout:
                continue
        else:
            raise TimeoutError("Failed to deliver data packet after retries")

        offset += len(chunk)
        seq ^= 1

    fin = _pack_packet(seq, FLAG_FIN, b"")
    for _ in range(MAX_RETRIES):
        sock.sendto(fin, peer_addr)
        try:
            raw, _ = sock.recvfrom(HEADER_SIZE + MAX_PAYLOAD)
            parsed = _unpack_packet(raw)
            if parsed and parsed[0] == seq and parsed[1] == FLAG_ACK:
                return
        except socket.timeout:
            continue

    raise TimeoutError("Failed to deliver end-of-transfer packet after retries")


def recv_bytes(sock: socket.socket, timeout: float = DEFAULT_TIMEOUT) -> tuple[bytes, tuple]:
    sock.settimeout(timeout)
    chunks = []
    expected_seq = 0
    peer_addr = None

    while True:
        try:
            raw, addr = sock.recvfrom(HEADER_SIZE + MAX_PAYLOAD)
        except socket.timeout:
            if chunks:
                raise TimeoutError("Transfer timed out waiting for data")
            raise

        if peer_addr is None:
            peer_addr = addr

        parsed = _unpack_packet(raw)
        if parsed is None:
            continue

        seq, flags, payload = parsed

        if flags == FLAG_ACK:
            continue

        if seq != expected_seq:
            if peer_addr is not None:
                _send_ack(sock, peer_addr, seq ^ 1)
            continue

        _send_ack(sock, peer_addr, seq)

        if flags == FLAG_FIN:
            break

        chunks.append(payload)
        expected_seq ^= 1

    return b"".join(chunks), peer_addr
