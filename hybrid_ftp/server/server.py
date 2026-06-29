import socket
import threading

from .auth import Authenticator
from .control import ControlChannel
from .session import Session

class FTPServer:
    def __init__(self, host="0.0.0.0", port=2121, authenticator=None):
        self.host = host
        self.port = port
        self.authenticator = authenticator or Authenticator()
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen()
        
        print(f"FTP Server listening on {self.host}:{self.port}")
        
        while True:
            client_sock, addr = self.sock.accept()
            thread = threading.Thread(
                target=self._handle_client,
                args=(client_sock, addr),
                daemon=True,
            )
            thread.start()
            
    def stop(self):
        self.sock.close()
            
    def _handle_client(self, client_sock, addr):
        session = Session(self.authenticator)
        
        try:
            control = ControlChannel(client_sock, session)
            print(f"[+] Client connected: {addr}")
            control.run()
        except Exception as e:
            print(f"[{addr}] {e}")

        finally:
            session.close_data_channel()
            client_sock.close()
            print(f"[-] Client disconnected: {addr}")