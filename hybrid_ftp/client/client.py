import os
import re
import socket
import time

from data import send_bytes, recv_bytes


class FTPClient:
    def __init__(self, host="127.0.0.1", port=2121, retry=5):
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
        self.data_host = None
        self.data_port = None

        print(self._read_response())

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

    def upload(self, local_path: str, remote_name: str | None = None):
        remote_name = remote_name or os.path.basename(local_path)
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)

        with open(local_path, "rb") as f:
            data = f.read()

        response = self.send(f"STOR {remote_name}")
        if self._response_code(response) != 150:
            raise RuntimeError(response)

        self._parse_data_endpoint(response)
        print(f"[data] Data endpoint {self.data_host}:{self.data_port}")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(30.0)
        peer = (self.data_host, self.data_port)

        print(f"[data] Uploading {len(data)} bytes...")
        send_bytes(sock, data, peer)
        sock.close()

        response = self._read_response()
        print(f"<<< {response}")
        return response

    def download(self, remote_name: str, local_path: str | None = None):
        local_path = local_path or remote_name

        response = self.send(f"RETR {remote_name}")
        if self._response_code(response) != 150:
            raise RuntimeError(response)

        self._parse_data_endpoint(response)
        print(f"[data] Data endpoint {self.data_host}:{self.data_port}")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(30.0)
        peer = (self.data_host, self.data_port)

        sock.sendto(b"READY", peer)
        print("[data] Downloading...")
        data, _ = recv_bytes(sock, timeout=30.0)
        sock.close()

        with open(local_path, "wb") as f:
            f.write(data)

        print(f"[data] Saved {len(data)} bytes to {local_path}")
        response = self._read_response()
        print(f"<<< {response}")
        return response

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

            if lower.startswith("put "):
                parts = line.split(maxsplit=2)
                if len(parts) < 2:
                    print("Usage: put <local_file> [remote_name]")
                    continue
                local_path = parts[1]
                remote_name = parts[2] if len(parts) == 3 else None
                try:
                    client.upload(local_path, remote_name)
                except Exception as exc:
                    print(f"Upload failed: {exc}")
                continue

            if lower.startswith("get "):
                parts = line.split(maxsplit=2)
                if len(parts) < 2:
                    print("Usage: get <remote_file> [local_file]")
                    continue
                remote_name = parts[1]
                local_path = parts[2] if len(parts) == 3 else None
                try:
                    client.download(remote_name, local_path)
                except Exception as exc:
                    print(f"Download failed: {exc}")
                continue

            response = client.send(line)
            code = client._response_code(response)
            if line.upper().startswith("USER") and code == 331:
                client.logged_in = False
            elif line.upper().startswith("PASS") and code == 230:
                client.logged_in = True

    except KeyboardInterrupt:
        print("\nForce quitting...")
    finally:
        client.close()


if __name__ == "__main__":
    main()
