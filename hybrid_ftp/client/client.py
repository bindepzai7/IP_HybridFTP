import socket
import time

class FTPClient:
    def __init__(self, host="127.0.0.1", port=2121, retry=5):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        for i in range(retry):
            try:
                self.sock.connect((host, port))
                print("Connected to FTP server")
                break
            except ConnectionRefusedError:
                print(f"Server not ready (attempt {i+1}/{retry}), retrying...")
                time.sleep(1)
        else:
            raise ConnectionError("Cannot connect to FTP server")

        self.buffer = ""

        print(self._read_response())

    def _read_response(self):
        lines = []

        while True:
            while "\r\n" not in self.buffer:
                data = self.sock.recv(4096).decode()
                if not data:
                    return "\n".join(lines)
                self.buffer += data

            line, self.buffer = self.buffer.split("\r\n", 1)
            lines.append(line)

            if len(line) >= 4 and line[3] == " " and line[:3].isdigit():
                break

        return "\n".join(lines)

    def send(self, cmd: str):
        self.sock.sendall((cmd + "\r\n").encode())
        return self._read_response()

    def close(self):
        self.sock.close()
        
def main():
    client = FTPClient()

    try:
        while True:
            line = input("ftp> ").strip()
            if not line:
                continue

            if line.lower() in ("exit", "quit"):
                if line.lower() == "quit":
                    print(client.send("QUIT"))
                break

            response = client.send(line)
            if response:
                print(response)

    except KeyboardInterrupt:
        print("\nForce quitting...")
    finally:
        client.close()


if __name__ == "__main__":
    main()