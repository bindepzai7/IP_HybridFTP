from enum import Enum
import os
import re
import struct
import zlib

_NEWLINE_RE = re.compile(rb"\r\n|\r|\n")


class AsciiCodec:
    """NVT-ASCII line-ending translation for TYPE A transfers.

    FTP defines the on-the-wire text format as canonical CRLF. Each endpoint
    converts between its own local newline convention and CRLF, so a text file
    stays correct when moved between platforms (e.g. Unix LF <-> Windows CRLF).

    Only applied when TYPE is A. TYPE I (Image/binary) is byte-exact and must
    never pass through this codec, or binary files would be corrupted.
    """

    @staticmethod
    def to_network(data: bytes) -> bytes:
        """Local text -> canonical CRLF for transmission."""
        return _NEWLINE_RE.sub(b"\r\n", data)

    @staticmethod
    def to_local(data: bytes) -> bytes:
        """Received CRLF -> this host's local newline convention."""
        text = data.replace(b"\r\n", b"\n")
        local = os.linesep.encode()
        if local != b"\n":
            text = text.replace(b"\n", local)
        return text


class TransferMode(Enum):
    STREAM = "S"
    BLOCK = "B"
    COMPRESSED = "C"

class TransferEngine:
    @staticmethod
    def encode_data(data: bytes, mode: TransferMode) -> bytes:
        if mode == TransferMode.BLOCK:
            result = bytearray()
            pointer = 0
            total_len = len(data)
            max_block_size = 65535
            
            if total_len == 0:
                return struct.pack("!BH", 0x80, 0)
                
            while pointer < total_len:
                chunk = data[pointer:pointer + max_block_size]
                pointer += len(chunk)
                descriptor = 0x80 if pointer >= total_len else 0x00
                result.extend(struct.pack("!BH", descriptor, len(chunk)))
                result.extend(chunk)
            return bytes(result)
            
        elif mode == TransferMode.COMPRESSED:
            return zlib.compress(data)
            
        return data

    @staticmethod
    def decode_data(data: bytes, mode: TransferMode) -> bytes:
        if mode == TransferMode.BLOCK:
            result = bytearray()
            pointer = 0
            total_len = len(data)
            
            while pointer < total_len:
                if pointer + 3 > total_len:
                    break
                descriptor, block_len = struct.unpack("!BH", data[pointer:pointer+3])
                pointer += 3
                
                if pointer + block_len > total_len:
                    raise ValueError("Block structure corrupted.")
                    
                result.extend(data[pointer:pointer+block_len])
                pointer += block_len
                
                if descriptor == 0x80:
                    break
            return bytes(result)
            
        elif mode == TransferMode.COMPRESSED:
            return zlib.decompress(data)
            
        return data