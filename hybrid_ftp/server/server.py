import socket

from control import ControlChannel
from auth import Authenticator
from session import Session


class FTPServer:
    def __init__(self, host="0.0.0.0", port=2121, authenticator=None):
        self.host = host
        self.port = port
        self.authenticator = authenticator or Authenticator()

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.settimeout(0.5)

    def start(self):
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen()
        print(f"Hybrid FTP server listening on {self.host}:{self.port}")

        try:
            while True:
                try:
                    client_sock, addr = self.server_sock.accept()
                except socket.timeout:
                    continue

                print(f"Client connected: {addr[0]}:{addr[1]}")
                ControlChannel(client_sock, Session(self.authenticator), addr).run()

        except KeyboardInterrupt:
            print("\nShutting down server...")

        finally:
            self.server_sock.close()


def main():
    authenticator = Authenticator()
    if not authenticator.user_exists("user"):
        authenticator.add_user("user", "password")
        print("Created default account: user / password")

    server = FTPServer(authenticator=authenticator)
    server.start()


if __name__ == "__main__":
    main()
