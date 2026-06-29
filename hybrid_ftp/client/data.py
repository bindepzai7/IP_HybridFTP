import socket
import struct

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
            raise RuntimeError("(send)Data channel has no peer.")
        self.sock.sendto(struct.pack("!I", len(data)), self.peer)
        try:
            for i in range(0, len(data), chunk_size):
                self.sock.sendto(data[i:i+chunk_size], self.peer)
        except KeyboardInterrupt:
            print("\n[Client] Interupting.")
            raise
        
    def receive(self) -> bytes:
        if self.peer is not None:
            meta = self.sock.recv(4)
        else:
            meta, addr = self.sock.recv(4)
            self.peer = addr
            self.sock.connect(addr) 
            
        total_size = struct.unpack("!I", meta)[0]
        
        buf = bytearray()
        while len(buf) < total_size:
            chunk, _ = self.sock.recvfrom(1024)
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)
    
    def close(self):
        self.sock.close()
        self.peer = None