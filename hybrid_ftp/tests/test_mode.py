"""
Unit tests for the transfer-mode codec (common/mode.py).

End-to-end integrity depends on encode/decode being lossless for every mode,
since the reliability layer only guarantees the *encoded* bytes arrive intact.
"""
import random

import pytest

from common.mode import TransferMode, TransferEngine


def _rand_bytes(n, seed):
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(n))


def _roundtrip(data, mode):
    encoded = TransferEngine.encode_data(data, mode)
    decoded = TransferEngine.decode_data(encoded, mode)
    assert decoded == data


ALL_MODES = [TransferMode.STREAM, TransferMode.BLOCK, TransferMode.COMPRESSED]


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize(
    "data",
    [
        b"",                          # empty
        b"hello ascii text",         # small text
        bytes(range(256)) * 10,      # small binary, all byte values
        _rand_bytes(20_000, seed=2), # larger random binary
    ],
    ids=["empty", "text", "binary256", "random20k"],
)
def test_roundtrip_all_modes(mode, data):
    _roundtrip(data, mode)


def test_block_multiblock():
    """> 65535 bytes forces multiple block descriptors (max block = 65535)."""
    _roundtrip(_rand_bytes(70_000, seed=1), TransferMode.BLOCK)


def test_block_exact_boundary():
    """Exactly one maximum-size block."""
    _roundtrip(b"\xAB" * 65535, TransferMode.BLOCK)
