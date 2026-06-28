"""
UDP data channel for basic-level file transfer.

First datagram: 4-byte big-endian total file size.
Following datagrams: raw file chunks (no ACKs or retransmission).
"""

import socket
import struct

MAX_PAYLOAD = 1024


class DataChannel:
    def __init__(self, udp_socket: socket.socket, peer_addr):
        self.udp_socket = udp_socket
        self.peer_addr = peer_addr

    def send(self, data: bytes) -> None:
        self.udp_socket.sendto(struct.pack("!I", len(data)), self.peer_addr)
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + MAX_PAYLOAD]
            self.udp_socket.sendto(chunk, self.peer_addr)
            offset += len(chunk)

    def signal_ready(self) -> None:
        self.udp_socket.sendto(b"READY", self.peer_addr)

    def receive(self) -> bytes:
        meta, _ = self.udp_socket.recvfrom(4)
        if len(meta) < 4:
            raise ValueError("Invalid size header")

        total = struct.unpack("!I", meta)[0]
        chunks = []
        received = 0

        while received < total:
            chunk, _ = self.udp_socket.recvfrom(MAX_PAYLOAD)
            chunks.append(chunk)
            received += len(chunk)

        return b"".join(chunks)[:total]

    def close(self) -> None:
        self.udp_socket.close()
