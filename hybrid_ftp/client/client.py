import os
import re
import socket
import time

from data import DataChannel

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "storage"))

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".py", ".html", ".htm", ".json", ".xml"}
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".zip", ".pdf", ".bin", ".exe", ".mp3", ".mp4", ".dat",
}


class FTPClient:
    def __init__(self, host="127.0.0.1", port=2121, retry=5):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        for i in range(retry):
            try:
                self.sock.connect((host, port))
                print(f"Connected to FTP server at {host}:{port}")
                break
            except ConnectionRefusedError:
                print(f"Server not ready (attempt {i + 1}/{retry}), retrying...")
                time.sleep(1)
        else:
            raise ConnectionError("Cannot connect to FTP server")

        self.buffer = ""
        self.logged_in = False
        self.transfer_type = "A"
        self.data_host = None
        self.data_port = None

        print(self._read_response())

    def _storage_path(self, filename: str) -> str:
        path = os.path.abspath(os.path.join(STORAGE_DIR, filename))
        if not path.startswith(STORAGE_DIR):
            raise ValueError("Path outside storage directory")
        return path

    def _read_response(self):
        lines = []

        while True:
            while "\r\n" not in self.buffer:
                data = self.sock.recv(4096).decode(errors="replace")
                if not data:
                    return "\n".join(lines)
                self.buffer += data

            line, self.buffer = self.buffer.split("\r\n", 1)
            lines.append(line)

            if len(line) >= 4 and line[3] == " " and line[:3].isdigit():
                break

        return "\n".join(lines)

    def _response_code(self, response: str) -> int:
        if response and response[:3].isdigit():
            return int(response[:3])
        return 0

    def send(self, cmd: str):
        print(f">>> {cmd}")
        self.sock.sendall((cmd + "\r\n").encode())
        response = self._read_response()
        print(f"<<< {response}")
        return response

    def _parse_data_endpoint(self, response: str):
        match = re.search(r"\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)", response)
        if not match:
            raise ValueError("No data endpoint in server response")

        host = ".".join(match.group(i) for i in range(1, 5))
        port = int(match.group(5)) * 256 + int(match.group(6))
        self.data_host = host
        self.data_port = port

    def _guess_transfer_type(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext in TEXT_EXTENSIONS:
            return "A"
        if ext in BINARY_EXTENSIONS:
            return "I"
        return "I"

    def set_transfer_type(self, transfer_type: str) -> None:
        transfer_type = transfer_type.upper()
        if transfer_type not in ("A", "I"):
            raise ValueError("Transfer type must be A or I")

        if transfer_type == self.transfer_type:
            return

        response = self.send(f"TYPE {transfer_type}")
        if self._response_code(response) != 200:
            raise RuntimeError(response)
        self.transfer_type = transfer_type

    def _ensure_transfer_type(self, filename: str) -> None:
        self.set_transfer_type(self._guess_transfer_type(filename))

    def upload(self, filename: str, remote_name: str | None = None):
        local_path = self._storage_path(filename)
        remote_name = remote_name or os.path.basename(filename)
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)

        with open(local_path, "rb") as f:
            data = f.read()

        self._ensure_transfer_type(filename)
        response = self.send(f"STOR {remote_name}")
        if self._response_code(response) != 150:
            raise RuntimeError(response)

        self._parse_data_endpoint(response)
        print(f"[data] Data endpoint {self.data_host}:{self.data_port}")
        peer = (self.data_host, self.data_port)

        print(f"[data] Uploading {len(data)} bytes...")
        channel = DataChannel(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), peer)
        channel.send(data)
        channel.close()

        response = self._read_response()
        print(f"<<< {response}")
        return response

    def download(self, remote_name: str, local_filename: str | None = None):
        local_filename = local_filename or remote_name
        local_path = self._storage_path(local_filename)

        self._ensure_transfer_type(local_filename)
        response = self.send(f"RETR {remote_name}")
        if self._response_code(response) != 150:
            raise RuntimeError(response)

        self._parse_data_endpoint(response)
        print(f"[data] Data endpoint {self.data_host}:{self.data_port}")
        peer = (self.data_host, self.data_port)

        channel = DataChannel(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), peer)
        channel.signal_ready()
        print("[data] Downloading...")
        data = channel.receive()
        channel.close()

        with open(local_path, "wb") as f:
            f.write(data)

        print(f"[data] Saved {len(data)} bytes to {local_path}")
        response = self._read_response()
        print(f"<<< {response}")
        return response

    def receive_data(self, command: str) -> bytes:
        response = self.send(command)
        if self._response_code(response) != 150:
            raise RuntimeError(response)

        self._parse_data_endpoint(response)
        peer = (self.data_host, self.data_port)

        channel = DataChannel(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), peer)
        channel.signal_ready()
        data = channel.receive()
        channel.close()

        response = self._read_response()
        print(f"<<< {response}")
        if self._response_code(response) != 226:
            raise RuntimeError(response)
        return data

    def list_directory(self, command: str = "LIST", path: str = "") -> str:
        cmd = command.upper()
        if path:
            cmd = f"{cmd} {path}"
        data = self.receive_data(cmd)
        text = data.decode(errors="replace")
        if text:
            print(text.rstrip())
        return text

    def close(self):
        self.sock.close()


def main():
    client = FTPClient()

    try:
        while True:
            line = input("ftp> ").strip()
            if not line:
                continue

            lower = line.lower()
            if lower in ("exit", "quit"):
                if lower == "quit":
                    print(client.send("QUIT"))
                break

            tokens = line.split()
            cmd = tokens[0].upper() if tokens else ""
            if cmd == "STOR":
                if len(tokens) == 2:
                    try:
                        client.upload(tokens[1])
                    except Exception as exc:
                        print(f"Upload failed: {exc}")
                else:
                    print("Usage: STOR <filename>")
                continue

            if cmd == "RETR":
                if len(tokens) == 2:
                    try:
                        client.download(tokens[1])
                    except Exception as exc:
                        print(f"Download failed: {exc}")
                else:
                    print("Usage: RETR <filename>")
                continue

            if cmd in ("LIST", "NLST"):
                path = tokens[1] if len(tokens) == 2 else ""
                try:
                    client.list_directory(cmd, path)
                except Exception as exc:
                    print(f"{cmd} failed: {exc}")
                continue

            response = client.send(line)
            code = client._response_code(response)
            if line.upper().startswith("USER") and code == 331:
                client.logged_in = False
            elif line.upper().startswith("PASS") and code == 230:
                client.logged_in = True
            elif line.upper().startswith("TYPE ") and code == 200:
                client.transfer_type = tokens[1].upper() if len(tokens) == 2 else client.transfer_type

    except KeyboardInterrupt:
        print("\nForce quitting...")
    finally:
        client.close()


if __name__ == "__main__":
    main()
