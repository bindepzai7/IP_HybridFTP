"""
UDP data channel for basic-level file transfer.

First datagram: 4-byte big-endian total file size.
Following datagrams: raw file chunks (no ACKs or retransmission).
"""

import socket
import struct

MAX_PAYLOAD = 1024
DEFAULT_TIMEOUT = 30.0


def send_bytes(sock: socket.socket, data: bytes, peer_addr) -> None:
    sock.sendto(struct.pack("!I", len(data)), peer_addr)
    offset = 0
    while offset < len(data):
        chunk = data[offset : offset + MAX_PAYLOAD]
        sock.sendto(chunk, peer_addr)
        offset += len(chunk)


def recv_bytes(sock: socket.socket, timeout: float = DEFAULT_TIMEOUT) -> tuple[bytes, tuple]:
    sock.settimeout(timeout)

    meta, addr = sock.recvfrom(4)
    if len(meta) < 4:
        raise ValueError("Invalid size header")

    total = struct.unpack("!I", meta)[0]
    chunks = []
    received = 0

    while received < total:
        chunk, _ = sock.recvfrom(MAX_PAYLOAD)
        chunks.append(chunk)
        received += len(chunk)

    return b"".join(chunks)[:total], addr
