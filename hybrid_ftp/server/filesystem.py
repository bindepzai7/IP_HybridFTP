"""
Server-side file system operations.

Handles file and directory management for the FTP server.
"""

import os
import stat
import time

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
ROOT_DIR = os.path.join(DATA_DIR, "root")


class FileSystem:
    def __init__(self):
        os.makedirs(ROOT_DIR, exist_ok=True)
        self.current_directory = ROOT_DIR

    def _in_root(self, path: str) -> bool:
        try:
            return os.path.commonpath([ROOT_DIR, path]) == ROOT_DIR
        except ValueError:
            return False

    def resolve_path(self, name: str) -> str:
        name = name.replace("\\", "/").strip()
        if name.startswith("/"):
            path = os.path.abspath(os.path.join(ROOT_DIR, name.lstrip("/")))
        else:
            path = os.path.abspath(os.path.join(self.current_directory, name))

        if not self._in_root(path):
            raise ValueError("Path outside server root")
        return path

    def display_path(self) -> str:
        rel = os.path.relpath(self.current_directory, ROOT_DIR)
        if rel == ".":
            return "/"
        return "/" + rel.replace("\\", "/")

    def pwd(self) -> str:
        return self.display_path()

    def cwd(self, path: str) -> None:
        target = self.resolve_path(path)
        if not os.path.isdir(target):
            raise FileNotFoundError(path)
        self.current_directory = target

    def cdup(self) -> None:
        parent = os.path.dirname(self.current_directory)
        if not self._in_root(parent) or len(parent) < len(ROOT_DIR):
            self.current_directory = ROOT_DIR
        else:
            self.current_directory = parent

    def mkdir(self, dirname: str) -> str:
        path = self.resolve_path(dirname)
        if os.path.exists(path):
            raise FileExistsError(dirname)
        os.makedirs(path)
        return self._path_to_display(path)

    def rmdir(self, dirname: str) -> None:
        path = self.resolve_path(dirname)
        if not os.path.isdir(path):
            raise FileNotFoundError(dirname)
        if os.listdir(path):
            raise OSError("Directory not empty")
        os.rmdir(path)

    def delete_file(self, filename: str) -> None:
        path = self.resolve_path(filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(filename)
        os.remove(path)

    def rename(self, old_name: str, new_name: str) -> None:
        old_path = self.resolve_path(old_name)
        new_path = self.resolve_path(new_name)
        if not os.path.exists(old_path):
            raise FileNotFoundError(old_name)
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        os.rename(old_path, new_path)

    def file_exists(self, filename: str) -> bool:
        try:
            return os.path.isfile(self.resolve_path(filename))
        except ValueError:
            return False

    def path_exists(self, name: str) -> bool:
        try:
            return os.path.exists(self.resolve_path(name))
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

    def file_size(self, filename: str) -> int:
        path = self.resolve_path(filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(filename)
        return os.path.getsize(path)

    def file_mtime(self, filename: str) -> str:
        path = self.resolve_path(filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(filename)
        return time.strftime("%Y%m%d%H%M%S", time.localtime(os.path.getmtime(path)))

    def _path_to_display(self, abs_path: str) -> str:
        rel = os.path.relpath(abs_path, ROOT_DIR)
        if rel == ".":
            return "/"
        return "/" + rel.replace("\\", "/")

    def _list_target(self, path: str | None) -> str:
        if not path:
            return self.current_directory
        return self.resolve_path(path)

    def _format_list_line(self, entry_path: str, name: str) -> str:
        st = os.stat(entry_path)
        mode = stat.S_IFDIR if stat.S_ISDIR(st.st_mode) else stat.S_IFREG
        type_char = "d" if mode == stat.S_IFDIR else "-"
        permissions = f"{type_char}rw-r--r--"
        size = 0 if stat.S_ISDIR(st.st_mode) else st.st_size
        mtime = time.strftime("%b %d %H:%M", time.localtime(st.st_mtime))
        return f"{permissions} 1 ftp ftp {size:>8} {mtime} {name}"

    def format_list(self, path: str | None = None) -> bytes:
        target = self._list_target(path)
        if not os.path.isdir(target):
            raise FileNotFoundError(path or self.display_path())

        lines = []
        for name in sorted(os.listdir(target)):
            lines.append(self._format_list_line(os.path.join(target, name), name))
        return ("\r\n".join(lines) + "\r\n").encode() if lines else b""

    def format_nlst(self, path: str | None = None) -> bytes:
        target = self._list_target(path)
        if not os.path.isdir(target):
            raise FileNotFoundError(path or self.display_path())

        names = sorted(os.listdir(target))
        return ("\r\n".join(names) + "\r\n").encode() if names else b""

    def format_file_stat(self, path: str) -> str:
        target = self.resolve_path(path)
        if not os.path.isfile(target):
            raise FileNotFoundError(path)

        st = os.stat(target)
        mtime = time.strftime("%Y%m%d%H%M%S", time.localtime(st.st_mtime))
        display = self._path_to_display(target)
        return (
            f" File: {display}\n"
            f" Size: {st.st_size}\n"
            f" Modified: {mtime}\n"
        )

    def format_directory_stat(self, path: str) -> str:
        target = self.resolve_path(path)
        if not os.path.isdir(target):
            raise FileNotFoundError(path)

        display = self._path_to_display(target)
        entries = os.listdir(target)
        lines = [f" Directory: {display}", f" Entries: {len(entries)}"]
        for name in sorted(entries):
            lines.append(self._format_list_line(os.path.join(target, name), name))
        return "\n".join(lines) + "\n"
