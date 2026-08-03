"""
Integration tests for the Reliable UDP layer (common/rdt.py).

A sender and receiver run on real loopback UDP sockets in two threads.
`LossySocket` wraps the sender's socket and randomly drops or corrupts
outgoing datagrams, proving the RDT layer recovers (retransmit) and
reassembles the stream in order without duplicates.

Loss is injected only on the sender->receiver (data) direction; ACKs travel
on a clean socket so the final FIN-ACK is never lost. Dropping the FIN-ACK
would expose the protocol's "last-ACK" limitation (the receiver ACKs the FIN
once then exits), which is a documented weakness rather than a test target.
"""
import random
import socket
import threading

import pytest

from common.rdt import ReliableUDP


class LossySocket:
    """Wraps a bound UDP socket; drops/corrupts a fraction of sendto() calls.

    Only sendto is degraded; everything else delegates to the real socket.
    A seeded RNG keeps runs reproducible.
    """

    def __init__(self, real_sock, drop_prob=0.0, corrupt_prob=0.0, seed=0):
        self._sock = real_sock
        self.drop_prob = drop_prob
        self.corrupt_prob = corrupt_prob
        self._rng = random.Random(seed)

    def settimeout(self, t):
        self._sock.settimeout(t)

    def sendto(self, data, addr):
        r = self._rng.random()
        if r < self.drop_prob:
            return len(data)  # pretend it was sent, but drop it
        if r < self.drop_prob + self.corrupt_prob:
            data = self._corrupt(data)
        return self._sock.sendto(data, addr)

    def recvfrom(self, n):
        return self._sock.recvfrom(n)

    def getsockname(self):
        return self._sock.getsockname()

    def close(self):
        self._sock.close()

    def _corrupt(self, data):
        b = bytearray(data)
        b[self._rng.randrange(len(b))] ^= 0xFF
        return bytes(b)


def _udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    return s


def _rand_bytes(n, seed):
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(n))


def _transfer(data, drop_prob=0.0, corrupt_prob=0.0, timeout=0.2):
    """Send `data` sender->receiver over loopback; return what arrived."""
    tx_raw, rx_raw = _udp(), _udp()
    tx = LossySocket(tx_raw, drop_prob, corrupt_prob, seed=1)  # lossy data path

    sender = ReliableUDP(tx, rx_raw.getsockname())
    receiver = ReliableUDP(rx_raw, tx_raw.getsockname())  # ACKs travel clean
    sender.TIMEOUT = timeout  # faster retransmit detection during tests

    received = {}

    def _recv():
        received["data"] = receiver.recv()

    t = threading.Thread(target=_recv, daemon=True)
    t.start()
    sender.send(data)
    t.join(timeout=30)

    tx.close()
    rx_raw.close()
    assert not t.is_alive(), "receiver did not finish (possible deadlock)"
    return received.get("data")


def test_small_clean():
    data = b"the quick brown fox jumps over the lazy dog"
    assert _transfer(data) == data


def test_empty():
    assert _transfer(b"") == b""


def test_multi_packet_clean():
    data = _rand_bytes(30 * 1024, seed=0)  # ~30 packets, no loss
    assert _transfer(data) == data


@pytest.mark.parametrize(
    "drop, corrupt",
    [
        (0.25, 0.0),   # data loss only
        (0.0, 0.25),   # corruption only
        (0.15, 0.15),  # both
    ],
    ids=["loss25", "corrupt25", "loss+corrupt"],
)
def test_recovers_from_degraded_link(drop, corrupt):
    data = _rand_bytes(20 * 1024, seed=7)
    assert _transfer(data, drop_prob=drop, corrupt_prob=corrupt) == data
