import socket

from control import ControlChannel
from auth import Authenticator
from session import Session


class FTPServer:
    def __init__(self, host="0.0.0.0", port=2121, authenticator=None):
        self.host = host
        self.port = port
        self.authenticator = authenticator

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.settimeout(0.5)  

    def start(self):
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen()

        print("Server running...")

        try:
            while True:
                try:
                    client_sock, addr = self.server_sock.accept()
                except socket.timeout:
                    continue

                print("Client:", addr)
                ControlChannel(client_sock, Session(self.authenticator)).run()

        except KeyboardInterrupt:
            print("\nShutting down server...")

        finally:
            self.server_sock.close()
            
def main():
    authenticator = Authenticator()
    server = FTPServer(authenticator=authenticator)
    server.start()

if __name__ == "__main__":
    main()