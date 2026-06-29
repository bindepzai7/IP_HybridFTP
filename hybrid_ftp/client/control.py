import socket

class ControlChannel:
    def __init__(self):
        self.socket = None
        self._recv_buffer = b""
        
    @property
    def connected(self):
        return self.sock is not None
    
    def _require_connection(self):
        if not self.connected:
            raise RuntimeError("Control channel is not connected.")
    
    def connect(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        
    def local_address(self):
        self._require_connection()
        return self.sock.getsockname()
        
    def send_line(self, line):
        self._require_connection()
        self.sock.sendall((line + "\r\n").encode("utf-8"))
        
    def read_line(self):
        self._require_connection()
        while b"\r\n" not in self._recv_buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Server closed the connection.")
            self._recv_buffer += chunk

        line, _, self._recv_buffer = self._recv_buffer.partition(b"\r\n")
        return line.decode("utf-8")
        
    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None