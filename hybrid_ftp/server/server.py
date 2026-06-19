import socket

from .control import ControlChannel
from .data import DataChannel

class FTPServer:
    control = ControlChannel
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.master_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        
    def start(self):
        while True:
            sock, addr = self.master_sock.accept()
            control = ControlChannel(sock, DataChannel)