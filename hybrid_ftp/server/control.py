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
            "PWD": self.handle_not_implemented,
            "CWD": self.handle_not_implemented,
            "CDUP": self.handle_not_implemented,
            "MKD": self.handle_not_implemented,
            "RMD": self.handle_not_implemented,
            "LIST": self.handle_not_implemented,
            "NLST": self.handle_not_implemented,
            "STAT": self.handle_not_implemented,
            "SIZE": self.handle_not_implemented,
            "MDTM": self.handle_not_implemented,
            "TYPE": self.handle_not_implemented,
            "MODE": self.handle_not_implemented,
            "PORT": self.handle_not_implemented,
            "PASV": self.handle_not_implemented,
            "RETR": self.handle_retr,
            "STOR": self.handle_stor,
            "STOU": self.handle_not_implemented,
            "APPE": self.handle_not_implemented,
            "DELE": self.handle_not_implemented,
            "RNFR": self.handle_not_implemented,
            "RNTO": self.handle_not_implemented,
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

    def handle_retr(self, args):
        if not self._require_login():
            return

        filename = args.strip()
        if not filename:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return

        if not self.fs.file_exists(filename):
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
            return

        try:
            file_data = self.fs.read_file(filename)
            file_data = file_data.replace(b"\n", b"\r\n").replace(b"\r\r\n", b"\r\n")

            host, port = self._open_data_channel()
            endpoint = self._format_data_endpoint(host, port)
            self._send_response(
                ReplyCode.OpeningData,
                f"Opening data connection for {filename} {endpoint}.",
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

        filename = args.strip()
        if not filename:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return

        try:
            host, port = self._open_data_channel()
            endpoint = self._format_data_endpoint(host, port)
            self._send_response(
                ReplyCode.OpeningData,
                f"Ready to receive {filename} {endpoint}.",
            )

            channel = DataChannel(self.session.data_socket)
            file_data = channel.receive_file()
            file_data = file_data.replace(b"\r\n", b"\n")

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
            text = "Supported basic commands: " + ", ".join(cmd.split()[0] for cmd in BASIC_COMMANDS)
            self._send_response(ReplyCode.CommandOK, text)
            return

        matches = [entry for entry in BASIC_COMMANDS if entry.startswith(topic)]
        if matches:
            self._send_response(ReplyCode.CommandOK, matches[0])
        else:
            self._send_response(ReplyCode.CommandNotImplemented, f"No help for {topic}.")

