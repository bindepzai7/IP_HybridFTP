import socket
from abc import ABC, abstractmethod
import struct
import time

MAX_PAYLOAD = 1024

class DataChannel(ABC):
    def __init__(self, sock):
        self.sock = sock
        self.peer = None
    
    @abstractmethod
    def establish(self):
        pass
    
    def send_bytes(self, data: bytes):
        if not self.peer:
            raise ValueError("Data channel is not established yet.")
        self.sock.sendto(data, self.peer)
        
    def send(self, data, chunk_size=1024):
        self.sock.send(struct.pack("!I", len(data)))

        for i in range(0, len(data), chunk_size):
            self.sock.send(data[i:i+chunk_size])
            time.sleep(0.001)
        
    def send_file(self, data: bytes, chunk_size=1024):
        if not self.peer:
            raise ValueError("Data channel is not established yet.")
        self.sock.sendto(struct.pack("!I", len(data)), self.peer)
        for i in range(0, len(data), chunk_size):
            self.sock.sendto(data[i:i + chunk_size], self.peer)
            time.sleep(0.001)
    
    def recv_bytes(self):
        data, addr = self.sock.recvfrom(MAX_PAYLOAD)
        if self.peer is not None and addr != self.peer:
            raise ValueError(f"Unexpected peer: {addr}")
        return data
    
    def close(self):
        self.peer = None
        self.sock.close()
        
class PassiveDataChannel(DataChannel):
    def establish(self):
        _, self.peer = self.sock.recvfrom(MAX_PAYLOAD)
        print(f"[Passive] Channel established with {self.peer}")
        
    # def recv_bytes(self):
    #     if hasattr(self, 'first_packet') and self.first_packet:
    #         data = self.first_packet
    #         self.first_packet = None
    #         return data
            
    #     return super().recv_bytes()

class ActiveDataChannel(DataChannel):
    def __init__(self, sock, host, port):
        super().__init__(sock)
        self.host = host
        self.port = port    
        
    def establish(self):
        self.peer = (self.host, self.port)
        print(f"[Active] Channel ready to send to {self.peer}")
