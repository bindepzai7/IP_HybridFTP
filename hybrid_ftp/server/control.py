import os
import socket

from reply_code import ReplyCode, DefaultMessage
from session import Session
from filesystem import FileSystem
from data import DataChannel

BASIC_COMMANDS = (
    "USER <username>",
    "PASS <password>",
    "QUIT",
    "NOOP",
    "PWD",
    "CWD <path>",
    "CDUP",
    "MKD <dirname>",
    "RMD <dirname>",
    "LIST [path]",
    "NLST [path]",
    "STAT [path]",
    "SIZE <filename>",
    "MDTM <filename>",
    "DELE <filename>",
    "RNFR <oldname>",
    "RNTO <newname>",
    "TYPE <type>",
    "RETR <filename>",
    "STOR <filename>",
    "HELP [command]",
)


class ControlChannel:
    def __init__(self, client_sock, session, client_addr=None):
        self.sock = client_sock
        self.session = session
        self.client_addr = client_addr
        self.fs = FileSystem()

        self.handlers = {
            "USER": self.handle_user,
            "PASS": self.handle_pass,
            "QUIT": self.handle_quit,
            "NOOP": self.handle_noop,
            "PWD": self.handle_pwd,
            "CWD": self.handle_cwd,
            "CDUP": self.handle_cdup,
            "MKD": self.handle_mkd,
            "RMD": self.handle_rmd,
            "LIST": self.handle_list,
            "NLST": self.handle_nlst,
            "STAT": self.handle_stat,
            "SIZE": self.handle_size,
            "MDTM": self.handle_mdtm,
            "TYPE": self.handle_type,
            "MODE": self.handle_not_implemented,
            "PORT": self.handle_not_implemented,
            "PASV": self.handle_not_implemented,
            "RETR": self.handle_retr,
            "STOR": self.handle_stor,
            "STOU": self.handle_not_implemented,
            "APPE": self.handle_not_implemented,
            "DELE": self.handle_dele,
            "RNFR": self.handle_rnfr,
            "RNTO": self.handle_rnto,
            "HASH": self.handle_not_implemented,
            "ABOR": self.handle_not_implemented,
            "HELP": self.handle_help,
        }

    def _process_command(self, line):
        line = line.strip()

        if not line:
            self._send_response(ReplyCode.CommandSyntaxError)
            return None

        cmd, _, arg = line.partition(" ")
        cmd = cmd.upper()
        arg = arg.strip()

        handler = self.handlers.get(cmd)

        if handler is None:
            self._send_response(ReplyCode.CommandNotImplemented)
            return None

        print(f"[{self.session.id[:8]}] {self.session.username or '-'} > {cmd} {arg}".rstrip())
        return handler(arg)

    def _send_response(self, code, custom_msg=None):
        if custom_msg is None:
            msg = DefaultMessage[code]
        else:
            msg = custom_msg

        response = f"{int(code)} {msg}\r\n"
        self.sock.sendall(response.encode())

    def _require_login(self) -> bool:
        if not self.session.logged_in:
            self._send_response(ReplyCode.NotLoggedIn)
            return False
        return True

    def _parse_path(self, args: str, required: bool = True) -> str | None:
        path = args.strip()
        if not path:
            if required:
                self._send_response(ReplyCode.ArgumentSyntaxError)
                return None
            return ""
        if " " in path:
            self._send_response(
                ReplyCode.ArgumentSyntaxError,
                "Path must not contain spaces.",
            )
            return None
        return path

    def _parse_filename(self, args: str) -> str | None:
        return self._parse_path(args, required=True)

    def _send_over_data(self, payload: bytes, opening_msg: str) -> bool:
        try:
            host, port = self._open_data_channel()
            endpoint = self._format_data_endpoint(host, port)
            self._send_response(
                ReplyCode.OpeningData,
                f"{opening_msg} Endpoint {endpoint}.",
            )
            channel = DataChannel(self.session.data_socket)
            channel.send_file(payload)
            self._send_response(ReplyCode.ClosingData, "Transfer complete.")
            return True
        except (TimeoutError, OSError, FileNotFoundError, ValueError) as exc:
            print(f"[data] Transfer failed: {exc}")
            self._send_response(ReplyCode.ConnectionClosed)
            return False
        finally:
            self.session.close_data_channel()

    def _data_host_for_reply(self) -> str:
        if self.session.data_host:
            return self.session.data_host
        if self.client_addr:
            return self.client_addr[0]
        host, _ = self.sock.getsockname()
        return "127.0.0.1" if host == "0.0.0.0" else host

    def _format_data_endpoint(self, host: str, port: int) -> str:
        parts = host.split(".")
        p1 = port // 256
        p2 = port % 256
        return f"({parts[0]},{parts[1]},{parts[2]},{parts[3]},{p1},{p2})"

    def _open_data_channel(self) -> tuple[str, int]:
        """Open the fixed UDP data channel (server listens, client connects)."""
        self.session.close_data_channel()

        data_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data_sock.bind(("0.0.0.0", 0))
        data_sock.settimeout(30.0)

        _, port = data_sock.getsockname()
        host = self._data_host_for_reply()

        self.session.data_socket = data_sock
        self.session.data_port = port
        self.session.data_host = host

        print(f"[data] UDP listening on {host}:{port}")
        return host, port

    def run(self):
        self._send_response(ReplyCode.SendUserCommand)

        while True:
            data = self.sock.recv(1024)
            if not data:
                break

            line = data.decode(errors="replace").strip()
            action = self._process_command(line)

            if action == "CLOSE":
                break

        self.session.close_data_channel()
        self.sock.close()

    def handle_not_implemented(self, _args):
        self._send_response(ReplyCode.CommandNotImplemented)

    def handle_user(self, line):
        username = line.strip()

        if not username:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return

        if self.session.logged_in:
            self._send_response(ReplyCode.BadCommandSequence, "Already logged in.")
            return

        if not self.session.authenticator.user_exists(username):
            self._send_response(ReplyCode.NotLoggedIn, "Invalid username.")
            return

        self.session.set_user(username)
        self._send_response(ReplyCode.SendPasswordCommand)

    def handle_pass(self, line):
        password = line.strip()
        if self.session.username is None:
            self._send_response(ReplyCode.BadCommandSequence)
            return

        ok = self.session.authenticator.authenticate(self.session.username, password)

        if not ok:
            self.session.set_user(None)
            self._send_response(ReplyCode.NotLoggedIn, "Login incorrect.")
            return

        self.session.login()
        self._send_response(ReplyCode.LoggedInProceed)

    def handle_quit(self, line):
        if line:
            self._send_response(ReplyCode.CommandSyntaxError)
            return

        self.session.logout()
        self._send_response(ReplyCode.ClosingControl)
        return "CLOSE"

    def handle_noop(self, _args):
        self._send_response(ReplyCode.CommandOK)

    def handle_pwd(self, _args):
        if not self._require_login():
            return
        path = self.fs.pwd()
        self._send_response(ReplyCode.PathnameCreated, f'"{path}" is the current directory.')

    def handle_cwd(self, args):
        if not self._require_login():
            return

        path = self._parse_path(args)
        if path is None:
            return

        try:
            self.fs.cwd(path)
            self._send_response(ReplyCode.FileActionOK, "Directory changed.")
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
        except ValueError:
            self._send_response(ReplyCode.ActionNotTakenFilenameNotAllowed)

    def handle_cdup(self, _args):
        if not self._require_login():
            return

        self.fs.cdup()
        self._send_response(ReplyCode.FileActionOK, "Directory changed.")

    def handle_mkd(self, args):
        if not self._require_login():
            return

        dirname = self._parse_path(args)
        if dirname is None:
            return

        try:
            created = self.fs.mkdir(dirname)
            self._send_response(ReplyCode.PathnameCreated, f'"{created}" created.')
        except FileExistsError:
            self._send_response(ReplyCode.ActionNotTakenFilenameNotAllowed, "Directory already exists.")
        except ValueError:
            self._send_response(ReplyCode.ActionNotTakenFilenameNotAllowed)

    def handle_rmd(self, args):
        if not self._require_login():
            return

        dirname = self._parse_path(args)
        if dirname is None:
            return

        try:
            self.fs.rmdir(dirname)
            self._send_response(ReplyCode.FileActionOK, "Directory removed.")
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
        except OSError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable, "Directory not empty.")

    def handle_list(self, args):
        if not self._require_login():
            return

        path = self._parse_path(args, required=False)
        if path is None:
            return

        try:
            listing = self.fs.format_list(path or None)
            self._send_over_data(listing, "Opening directory list.")
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)

    def handle_nlst(self, args):
        if not self._require_login():
            return

        path = self._parse_path(args, required=False)
        if path is None:
            return

        try:
            listing = self.fs.format_nlst(path or None)
            self._send_over_data(listing, "Opening name list.")
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)

    def handle_stat(self, args):
        if not self._require_login():
            return

        path = self._parse_path(args, required=False)
        if path is None:
            return

        try:
            if not path:
                transfer = "ASCII" if self.session.type == "A" else "Image"
                info = (
                    f"Hybrid FTP server status.\n"
                    f" User: {self.session.username}\n"
                    f" Current directory: {self.fs.display_path()}\n"
                    f" Transfer type: {transfer}\n"
                )
                self._send_response(ReplyCode.SystemStatus, info)
                return

            target = self.fs.resolve_path(path)
            if os.path.isdir(target):
                info = self.fs.format_directory_stat(path)
                self._send_response(ReplyCode.DirectoryStatus, info)
            elif os.path.isfile(target):
                info = self.fs.format_file_stat(path)
                self._send_response(ReplyCode.FileStatus, info)
            else:
                self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
        except (FileNotFoundError, ValueError):
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)

    def handle_size(self, args):
        if not self._require_login():
            return

        filename = self._parse_path(args)
        if filename is None:
            return

        try:
            size = self.fs.file_size(filename)
            self._send_response(ReplyCode.FileStatus, str(size))
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)

    def handle_mdtm(self, args):
        if not self._require_login():
            return

        filename = self._parse_path(args)
        if filename is None:
            return

        try:
            mtime = self.fs.file_mtime(filename)
            self._send_response(ReplyCode.FileStatus, mtime)
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)

    def handle_dele(self, args):
        if not self._require_login():
            return

        filename = self._parse_path(args)
        if filename is None:
            return

        try:
            self.fs.delete_file(filename)
            self._send_response(ReplyCode.FileActionOK, "File deleted.")
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)

    def handle_rnfr(self, args):
        if not self._require_login():
            return

        old_name = self._parse_path(args)
        if old_name is None:
            return

        if not self.fs.path_exists(old_name):
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
            return

        self.session.rename_from = old_name
        self._send_response(ReplyCode.FileCommandPending, "File marked for rename.")

    def handle_rnto(self, args):
        if not self._require_login():
            return

        if self.session.rename_from is None:
            self._send_response(ReplyCode.BadCommandSequence, "RNFR required before RNTO.")
            return

        new_name = self._parse_path(args)
        if new_name is None:
            return

        try:
            self.fs.rename(self.session.rename_from, new_name)
            self.session.rename_from = None
            self._send_response(ReplyCode.FileActionOK, "Rename complete.")
        except FileNotFoundError:
            self.session.rename_from = None
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
        except ValueError:
            self.session.rename_from = None
            self._send_response(ReplyCode.ActionNotTakenFilenameNotAllowed)

    def handle_type(self, args):
        if not self._require_login():
            return

        transfer_type = args.strip().upper()
        if transfer_type not in ("A", "I"):
            self._send_response(ReplyCode.ArgumentSyntaxError, "TYPE must be A or I.")
            return

        self.session.type = transfer_type
        label = "ASCII" if transfer_type == "A" else "Binary"
        self._send_response(ReplyCode.CommandOK, f"Type set to {label}.")

    def _prepare_outgoing_data(self, file_data: bytes) -> bytes:
        if self.session.type == "A":
            return file_data.replace(b"\n", b"\r\n").replace(b"\r\r\n", b"\r\n")
        return file_data

    def _prepare_incoming_data(self, file_data: bytes) -> bytes:
        if self.session.type == "A":
            return file_data.replace(b"\r\n", b"\n")
        return file_data

    def handle_retr(self, args):
        if not self._require_login():
            return

        filename = self._parse_filename(args)
        if filename is None:
            return

        if not self.fs.file_exists(filename):
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
            return

        try:
            file_data = self._prepare_outgoing_data(self.fs.read_file(filename))

            host, port = self._open_data_channel()
            endpoint = self._format_data_endpoint(host, port)
            self._send_response(
                ReplyCode.OpeningData,
                f'Opening data connection for "{filename}". Endpoint {endpoint}.',
            )

            channel = DataChannel(self.session.data_socket)
            channel.send_file(file_data)
            self._send_response(ReplyCode.ClosingData, "Transfer complete.")
        except (TimeoutError, OSError) as exc:
            print(f"[data] RETR failed: {exc}")
            self._send_response(ReplyCode.ConnectionClosed)
        finally:
            self.session.close_data_channel()

    def handle_stor(self, args):
        if not self._require_login():
            return

        filename = self._parse_filename(args)
        if filename is None:
            return

        try:
            host, port = self._open_data_channel()
            endpoint = self._format_data_endpoint(host, port)
            self._send_response(
                ReplyCode.OpeningData,
                f'Ready to receive "{filename}". Endpoint {endpoint}.',
            )

            channel = DataChannel(self.session.data_socket)
            file_data = self._prepare_incoming_data(channel.receive_file())

            self.fs.write_file(filename, file_data)
            self._send_response(ReplyCode.ClosingData, "Transfer complete.")
        except (TimeoutError, OSError) as exc:
            print(f"[data] STOR failed: {exc}")
            self._send_response(ReplyCode.ConnectionClosed)
        finally:
            self.session.close_data_channel()

    def handle_help(self, args):
        topic = args.strip().upper()
        if not topic:
            text = "Supported commands: " + ", ".join(cmd.split()[0] for cmd in BASIC_COMMANDS)
            self._send_response(ReplyCode.CommandOK, text)
            return

        matches = [entry for entry in BASIC_COMMANDS if entry.startswith(topic)]
        if matches:
            self._send_response(ReplyCode.CommandOK, matches[0])
        else:
            self._send_response(ReplyCode.CommandNotImplemented, f"No help for {topic}.")

