from dataclasses import dataclass
import struct
import zlib

FLAG_DATA = 0x01
FLAG_ACK = 0x02
FLAG_FIN = 0x04

HEADER_FORMAT = "!IIBHI"
HEADER_NO_CSUM_FORMAT = "!IIBH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

@dataclass
class Packet: 
    seq: int = 0
    ack: int = 0
    flags: int = 0
    payload: bytes = b""
    
    @property
    def length(self):
        return len(self.payload)
    
    @property
    def is_ack(self):
        return bool(self.flags & FLAG_ACK)

    @property
    def is_data(self):
        return bool(self.flags & FLAG_DATA)

    @property
    def is_fin(self):
        return bool(self.flags & FLAG_FIN)
    
    def compute_checksum(self):
        header = struct.pack(
            HEADER_NO_CSUM_FORMAT,
            self.seq, 
            self.ack, 
            self.flags,
            self.length, 
        )
        return zlib.crc32(header + self.payload) & 0xFFFFFFFF
    
    def to_bytes(self) -> bytes:
        header = struct.pack(
            HEADER_FORMAT,
            self.seq,
            self.ack,
            self.flags,
            self.length,
            self.compute_checksum(),
        )
        return header + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "Packet": 
        if len(data) < HEADER_SIZE:
            raise ValueError("Incomplete packet header.")
        
        seq, ack, flags, length, checksum = struct.unpack(
            HEADER_FORMAT,
            data[:HEADER_SIZE],
        )
        
        expected_size = length + HEADER_SIZE
        if len(data) != expected_size:
            raise ValueError(
                f"Packet length mismatch: expected {expected_size} bytes, got {len(data)}."
            )
            
        payload = data[HEADER_SIZE:]
        
        packet = cls(
            seq=seq,
            ack=ack,
            flags=flags,
            payload=payload,
        )
        
        if checksum != packet.compute_checksum():
            raise ValueError("Checksum mismatch.")
        
        return packet
    
    def __repr__(self):
        return (
            f"Packet(seq={self.seq}, "
            f"ack={self.ack}, "
            f"flags={self.flags:#04x}, "
            f"payload={len(self.payload)} bytes)"
        )