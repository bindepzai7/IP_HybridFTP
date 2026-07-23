import socket
import logging
from typing import Optional

from packet import Packet, FLAG_DATA, FLAG_ACK, FLAG_FIN


class ReliableUDP:
    MAX_PAYLOAD_SIZE = 1024
    MAX_PACKET_SIZE = 2048
    TIMEOUT = 1.0
    MAX_RETRIES = 20

    def __init__(
        self,
        sock: socket.socket,
        target_addr: Optional[tuple[str, int]] = None,
    ):
        self.socket = sock
        self.target_addr = target_addr
        self.socket.settimeout(self.TIMEOUT)

    def send(self, data: bytes) -> None:
        seq = 0
        offset = 0

        while offset < len(data):
            chunk = data[offset : offset + self.MAX_PAYLOAD_SIZE]

            packet = Packet(
                seq=seq,
                flags=FLAG_DATA,
                payload=chunk,
            )

            self._send_with_retry(packet)

            seq ^= 1
            offset += len(chunk)

        self._send_fin(seq)

    def recv(self) -> bytes:
        expected_seq = 0
        data = bytearray()

        while True:
            packet = self._recv_valid_packet()

            if packet is None:
                continue

            if packet.is_fin:
                logging.debug("Received FIN")
                self._acknowledge(packet.seq)
                break

            if not packet.is_data:
                continue

            if packet.seq == expected_seq:
                data.extend(packet.payload)
                expected_seq ^= 1

            self._acknowledge(packet.seq)

        return bytes(data)

    def close(self) -> None:
        self.socket.close()

    def _send_with_retry(self, packet: Packet) -> None:
        retries = 0

        while retries < self.MAX_RETRIES:
            self.send_packet(packet)

            try:
                if self._wait_for_ack(packet.seq):
                    return

            except socket.timeout:
                retries += 1
                logging.debug(
                    f"Timeout waiting for ACK {packet.seq} "
                    f"(attempt {retries}/{self.MAX_RETRIES})"
                )

        raise TimeoutError(
            f"Failed to deliver packet seq={packet.seq}"
        )

    def _wait_for_ack(self, expected_ack: int) -> bool:
        while True:
            packet = self._recv_valid_packet()

            if packet is None:
                continue

            if (
                packet.is_ack
                and packet.ack == expected_ack
            ):
                return True

    def _send_fin(self, seq: int) -> None:
        fin_packet = Packet(
            seq=seq,
            flags=FLAG_FIN,
        )

        self._send_with_retry(fin_packet)

    def _acknowledge(self, seq: int) -> None:
        ack_packet = Packet(
            ack=seq,
            flags=FLAG_ACK,
        )

        self.send_packet(ack_packet)

    def _recv_valid_packet(self) -> Optional[Packet]:
        try:
            return self.recv_packet()

        except socket.timeout:
            raise

        except ValueError as exc:
            logging.debug(
                f"Discarding corrupted packet: {exc}"
            )
            return None

    def send_packet(self, packet: Packet) -> None:
        if self.target_addr is None:
            raise ValueError(
                "Target address is not configured."
            )

        self.socket.sendto(
            packet.to_bytes(),
            self.target_addr,
        )

    def recv_packet(self) -> Packet:
        raw_data, sender_addr = self.socket.recvfrom(
            self.MAX_PACKET_SIZE
        )

        if self.target_addr is None:
            self.target_addr = sender_addr

        return Packet.from_bytes(raw_data)