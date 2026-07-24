import socket
from abc import ABC, abstractmethod
import struct
import time
from common.rdt import ReliableUDP

MAX_PAYLOAD = 1024

class DataChannel(ABC):
    def __init__(self, sock):
        self.sock = sock
        self.peer = None
    
    @abstractmethod
    def establish(self):
        pass
        

    def send_file(self, data: bytes, chunk_size=1024):
        if not self.peer:
            raise ValueError("Data channel is not established yet.")
        ReliableUDP(self.sock, self.peer).send(data)
    
    def recv_file(self):
        if not self.peer:
            raise ValueError("Data channel is not established yet.")
        return ReliableUDP(self.sock, self.peer).recv()
    
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
