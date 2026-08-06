import os
import re

from .data import DataChannel
from .control import ControlChannel
from common.mode import TransferMode, TransferEngine, AsciiCodec
import hashlib

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "storage"))
os.makedirs(STORAGE_DIR, exist_ok=True)

class FTPClient:
    def __init__(self, verbose_hash=False):
        self.control = ControlChannel()
        self.data = None
        self.mode = TransferMode.STREAM
        # Default to binary (Image) so no file is ever corrupted by accident;
        # TYPE A opts into ASCII newline translation. (RFC 959 defaults to A,
        # but binary-by-default avoids the classic ASCII-corrupts-binaries trap.)
        self.type = "I"
        # When False, a successful integrity check stays silent (like pip/apt);
        # a MISMATCH is always reported. Enable with the --verify_hash CLI flag.
        self.verbose_hash = verbose_hash

    def _sha256_file(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def verify_hash(self, remote_name: str, local_path: str) -> bool:
        # Send HASH quietly (bypass _send_cmd's echo) so the report below
        # is the only integrity output the user sees.
        self.control.send_line(f"HASH {remote_name}")
        resp = self.control.read_line()

        if not resp.startswith("213"):
            if self.verbose_hash:
                print(f"[Verify] skipped - server could not hash '{remote_name}': {resp}")
            return False

        server_hash = resp.split()[-1].lower()   # "213 SHA256 <hex>" -> <hex>
        local_hash = self._sha256_file(local_path).lower()

        if server_hash == local_hash:
            if self.verbose_hash:
                print(f"[Verify] SHA-256 MATCH - '{remote_name}' transferred intact")
                print(f"         {local_hash}")
            return True

        # A mismatch means corruption slipped through - always report it.
        print(f"[Verify] SHA-256 MISMATCH - '{remote_name}' may be corrupted")
        print(f"         local : {local_hash}")
        print(f"         server: {server_hash}")
        return False
            
    def connect(self, host, port):
        self.control.connect(host, port)
        
    def disconnect_data(self):
        if self.data is not None:
            try:
                self.data.sock.close()
            except Exception:
                pass
            self.data = None

    def disconnect(self):
        self.disconnect_data()
        self.control.close()
        
    def _send_cmd(self, cmd_line: str) -> str:
        self.control.send_line(cmd_line)
        resp = self.control.read_line()
        print(resp)
        return resp
    
    def _storage_path(self, filename: str) -> str:
        path = os.path.abspath(os.path.join(STORAGE_DIR, filename))
        if not path.startswith(STORAGE_DIR):
            raise ValueError("Path traversal detected.")
        return path
    
    def _finish_transfer(self):
        final = self.control.read_line()
        print(final)
        self.disconnect_data()
        
    def _expect(self, response, *codes):
        if not any(response.startswith(code) for code in codes):
            raise RuntimeError(response)
    
    def set_passive_mode(self) -> tuple[str, int]:
        resp = self._send_cmd("PASV")
        if not resp.startswith("227"):
            raise RuntimeError(f"PASV failed: {resp}")
        m = re.search(r"\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)", resp)
        if not m:
            raise RuntimeError(f"Invalid PASV response: {resp}")
        host = ".".join(m.group(1, 2, 3, 4))
        port = int(m.group(5)) * 256 + int(m.group(6))
        
        if host == "0.0.0.0":
            host = self.control.sock.getpeername()[0]
        
        self.disconnect_data()
        self.data = DataChannel()
        self.data.bind()
        self.data.set_peer(host, port)

        print(f"[Data] Passive mode set to {host}:{port}")
        return host, port
    
    def set_active_mode(self, port_str: str) -> tuple[str, int]:
        parts = port_str.split(",")
        if len(parts) != 6:
            raise ValueError("Syntax Error: h1,h2,h3,h4,p1,p2")
        host = ".".join(parts[:4])
        port = int(parts[4])*256 + int(parts[5])
        
        self.disconnect_data()
        self.data = DataChannel()
        self.data.bind(host, port)
        actual_port = self.data.local_port()
        
        ip_parts = host.replace(".", ",")
        p1, p2 = actual_port // 256, actual_port % 256
        cmd = f"PORT {ip_parts},{p1},{p2}"
        
        resp = self._send_cmd(cmd)
        self._expect(resp, "200")

        print(f"[Data] Active: listening on {host}:{actual_port}")
        return host, actual_port    

    def _ensure_data_channel(self):
        """Default to passive mode when no data channel is set up yet.

        Mirrors how real FTP clients (ftplib, lftp, browsers) auto-negotiate a
        data connection per transfer instead of requiring a manual PASV/PORT.
        An explicit PASV or PORT beforehand is still honored, since it sets
        self.data and this becomes a no-op.
        """
        if self.data is None:
            self.set_passive_mode()

    def set_transfer_mode(self, mode_char: str):
        mode_char = mode_char.upper()
        try:
            target_mode = TransferMode(mode_char)
        except ValueError:
            print("Invalid mode. Use S, B, or C.")
            return

        resp = self._send_cmd(f"MODE {mode_char}")

        if resp.startswith("200"):
            self.mode = target_mode
            print(f"[Client] Internal mode updated to {target_mode.name}")

    def set_type(self, type_char: str):
        type_char = type_char.upper()
        if type_char not in ("A", "I"):
            print("Invalid type. Use A (ASCII) or I (Image/binary).")
            return

        resp = self._send_cmd(f"TYPE {type_char}")
        if resp.startswith("200"):
            self.type = type_char
            label = "ASCII" if type_char == "A" else "Binary"
            print(f"[Client] Transfer type set to {label}.")

    def _maybe_verify_hash(self, remote_name, local_path):
        """Hash verification is only meaningful for byte-exact (binary) transfers.
        In ASCII mode the two sides' files differ by newline convention, so the
        SHA-256 digests would legitimately not match -- skip the check."""
        if self.type == "I":
            self.verify_hash(remote_name, local_path)
        elif self.verbose_hash:
            print("[Verify] skipped - integrity hash applies to binary (TYPE I) transfers only")

    def retr(self, remote_name, local_filename):
        self._ensure_data_channel()
        
        local_filename = local_filename or remote_name
        local_path = self._storage_path(local_filename)
        
        resp = self._send_cmd(f"RETR {remote_name}")
        self._expect(resp, "125", "150")
        data_bytes = self.data.receive()
        raw_data = TransferEngine.decode_data(data_bytes, self.mode)
        if self.type == "A":
            raw_data = AsciiCodec.to_local(raw_data)

        with open(local_path, "wb") as f:
            f.write(raw_data)
        print(f"[Client] Saved → storage/{local_filename}")

        self._finish_transfer()
        self._maybe_verify_hash(remote_name, local_path)
        
    def stor(self, local_filename, remote_name):
        self._ensure_data_channel()
        
        local_path = self._storage_path(local_filename)
        remote_name = remote_name or os.path.basename(local_filename)
        
        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Not found: {local_path}")
        
        with open(local_path, "rb") as f:
            raw_data = f.read()
        if self.type == "A":
            raw_data = AsciiCodec.to_network(raw_data)

        payload = TransferEngine.encode_data(raw_data, self.mode)

        resp = self._send_cmd(f"STOR {remote_name}")

        self._expect(resp, "125", "150")
        self.data.send(payload)
        print(f"[Client] Sent {len(payload)} (encoded) bytes → {remote_name}")
        self._finish_transfer()
        self._maybe_verify_hash(remote_name, local_path)
    
    def list_dir(self, path: str = ""):
        self._ensure_data_channel()
        
        cmd = f"LIST {path}".strip()
        resp = self._send_cmd(cmd)
        self._expect(resp, "125", "150")
        
        raw = self.data.receive()
        print(raw.decode("utf-8", errors="replace"))
        
        self._finish_transfer()
    
    def nlst(self, path: str=""):
        self._ensure_data_channel()

        cmd = f"NLST {path}".strip()
        resp = self._send_cmd(cmd)
        if not resp.startswith("150"):
            return

        raw = self.data.receive()
        print(raw.decode("utf-8", errors="replace"))

        final = self.control.read_line()
        print(final)
        self.disconnect_data()
        
    def appe(self, local_filename, remote_name):
        self._ensure_data_channel()
        
        local_path = self._storage_path(local_filename)
        remote_name = remote_name or os.path.basename(local_filename)
        
        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Not found: {local_path}")
        
        with open(local_path, "rb") as f:
            raw_data = f.read()
        if self.type == "A":
            raw_data = AsciiCodec.to_network(raw_data)
        payload = TransferEngine.encode_data(raw_data, self.mode)
        resp = self._send_cmd(f"APPE {remote_name}")
        
        self._expect(resp, "125", "150")
        self.data.send(payload)
        print(f"[Client] Appended {len(payload)} bytes → {remote_name}")
        self._finish_transfer()
        
    def stou(self, local_filename):
        self._ensure_data_channel()
        
        local_path = self._storage_path(local_filename)
        
        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Not found: {local_path}")
        
        with open(local_path, "rb") as f:
            raw_data = f.read()
        if self.type == "A":
            raw_data = AsciiCodec.to_network(raw_data)

        payload = TransferEngine.encode_data(raw_data, self.mode)

        resp = self._send_cmd("STOU")
        
        self._expect(resp, "125", "150")
        self.data.send(payload)
        print(f"[Client] Sent {len(payload)} bytes (STOU)")
        self._finish_transfer()
        
    def abort(self):
        print("[Client] Sending ABOR...")
        self.control.send_line("ABOR")
        while True:
            resp = self.control.read_line()
            print(resp)
            if resp.startswith("225") or resp.startswith("226"):
                break
        self.disconnect_data()