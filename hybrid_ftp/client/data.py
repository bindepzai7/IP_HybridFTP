import socket
import struct
import time
from common.rdt import ReliableUDP

class DataChannel:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.peer = None
        
    def bind(self, host="0.0.0.0", port=0):
        self.sock.bind((host,port))

    def local_port(self):
        return self.sock.getsockname()[1]

    def set_peer(self, host, port):
        self.peer = (host, port)
        self.sock.connect((host, port))
        self.sock.send(b"\x00")
        
    def send(self, data: bytes, chunk_size=1024):
        if self.peer is None:
            raise RuntimeError("Data channel has no peer.")
        ReliableUDP(self.sock, self.peer).send(data)
        
    def receive(self) -> bytes:
        return ReliableUDP(self.sock, self.peer).recv()
    