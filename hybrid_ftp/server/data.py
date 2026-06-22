"""
UDP data channel for basic-level file transfer.

First datagram: 4-byte big-endian total file size.
Following datagrams: raw file chunks (no ACKs or retransmission).
"""

import socket
import struct

MAX_PAYLOAD = 1024
DEFAULT_TIMEOUT = 30.0


class DataChannel:
    def __init__(self, data_socket: socket.socket, timeout: float = DEFAULT_TIMEOUT):
        self.udp_socket = data_socket
        self.timeout = timeout
        self.udp_socket.settimeout(timeout)

    def _wait_for_peer(self) -> tuple:
        try:
            _, addr = self.udp_socket.recvfrom(MAX_PAYLOAD)
            return addr
        except socket.timeout:
            raise TimeoutError("Timed out waiting for data connection")

    def _send_bytes(self, data: bytes, peer_addr) -> None:
        self.udp_socket.sendto(struct.pack("!I", len(data)), peer_addr)
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + MAX_PAYLOAD]
            self.udp_socket.sendto(chunk, peer_addr)
            offset += len(chunk)

    def _recv_bytes(self) -> tuple[bytes, tuple]:
        meta, addr = self.udp_socket.recvfrom(4)
        if len(meta) < 4:
            raise ValueError("Invalid size header")

        total = struct.unpack("!I", meta)[0]
        chunks = []
        received = 0

        while received < total:
            chunk, _ = self.udp_socket.recvfrom(MAX_PAYLOAD)
            chunks.append(chunk)
            received += len(chunk)

        return b"".join(chunks)[:total], addr

    def send_file(self, data: bytes) -> None:
        peer_addr = self._wait_for_peer()
        self._send_bytes(data, peer_addr)
        print(f"[data] Sent {len(data)} bytes to {peer_addr}")

    def receive_file(self) -> bytes:
        data, peer_addr = self._recv_bytes()
        print(f"[data] Received {len(data)} bytes from {peer_addr}")
        return data
