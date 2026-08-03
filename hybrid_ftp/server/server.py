import socket
import threading

from .auth import Authenticator
from .control import ControlChannel
from .session import Session
from .registry import SessionRegistry

class FTPServer:
    def __init__(self, host="0.0.0.0", port=2121, authenticator=None):
        self.host = host
        self.port = port
        self.authenticator = authenticator or Authenticator()
        self.registry = SessionRegistry()
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._running = False

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen()
        self._running = True

        print(f"FTP Server listening on {self.sock.getsockname()}")

        while self._running:
            try:
                client_sock, addr = self.sock.accept()
            except OSError:
                if not self._running:
                    break  # socket closed by stop() during shutdown
                raise
            thread = threading.Thread(
                target=self._handle_client,
                args=(client_sock, addr),
                daemon=True,
            )
            thread.start()

    def stop(self):
        self._running = False
        self.sock.close()
            
    def _handle_client(self, client_sock, addr):
        session = Session(self.authenticator)
        session.remote_addr = addr

        try:
            control = ControlChannel(
                client_sock, session, client_addr=addr, registry=self.registry
            )
            self.registry.add(session)
            print(f"[+] Client connected: {addr}")
            self.registry.print_table()
            control.run()
        except Exception as e:
            print(f"[{addr}] {e}")

        finally:
            self.registry.remove(session)
            session.close_data_channel()
            client_sock.close()
            print(f"[-] Client disconnected: {addr}")
            self.registry.print_table()