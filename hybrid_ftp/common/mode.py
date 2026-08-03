from enum import Enum
import struct
import zlib

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