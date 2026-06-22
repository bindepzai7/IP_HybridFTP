"""
Server-side file system operations.

Handles file and directory management for the FTP server.
"""

import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))


class FileSystem:
    def __init__(self):
        os.makedirs(ROOT_DIR, exist_ok=True)
        self.current_directory = ROOT_DIR

    def resolve_path(self, filename: str) -> str:
        path = os.path.abspath(os.path.join(self.current_directory, filename))
        if not path.startswith(ROOT_DIR):
            raise ValueError("Path outside server root")
        return path

    def file_exists(self, filename: str) -> bool:
        try:
            return os.path.isfile(self.resolve_path(filename))
        except ValueError:
            return False

    def read_file(self, filename: str) -> bytes:
        path = self.resolve_path(filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(filename)
        with open(path, "rb") as f:
            return f.read()

    def write_file(self, filename: str, data: bytes) -> None:
        path = self.resolve_path(filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
