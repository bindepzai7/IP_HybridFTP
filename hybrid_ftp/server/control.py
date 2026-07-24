import os
import socket
import struct
import zlib

from .reply_code import ReplyCode, DefaultMessage
from .data import ActiveDataChannel, PassiveDataChannel, MAX_PAYLOAD
from common.mode import TransferMode, TransferEngine

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
        # self.session.fs = FileSystem()

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
            "MODE": self.handle_mode,
            "PORT": self.handle_port,
            "PASV": self.handle_pasv,
            "RETR": self.handle_retr,
            "STOR": self.handle_stor,
            "STOU": self.handle_stou,
            "APPE": self.handle_appe,
            "DELE": self.handle_dele,
            "RNFR": self.handle_rnfr,
            "RNTO": self.handle_rnto,
            "HASH": self.handle_hash,
            "ABOR": self.handle_abor,
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
    
    def _require_data_connection(self):
        if self.session.data_channel is None:
            self._send_response(ReplyCode.CantOpenData)
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

    # def _parse_filename(self, args: str) -> str | None:
    #     return self._parse_path(args, required=True)

    def _send_over_data(self, payload: bytes, opening_msg: str) -> bool:
        if not self._require_data_connection():
            return False
        try:
            self._send_response(ReplyCode.OpeningData, opening_msg)
            
            self.session.data_channel.establish()
            self.session.data_channel.send_file(payload)
            
            self._send_response(ReplyCode.ClosingData)
            return True
        except Exception as exc:
            print(f"[data] Transfer failed: {exc}")
            self._send_response(ReplyCode.ConnectionClosed, "Transfer aborted.")
            return False
        finally:
            self.session.close_data_channel()

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

    def handle_noop(self, line):
        if line:
            self._send_response(ReplyCode.CommandSyntaxError)
            return 
        self._send_response(ReplyCode.CommandOK)

    def handle_pwd(self, _args):
        if not self._require_login():
            return
        path = self.session.fs.pwd()
        self._send_response(ReplyCode.PathnameCreated, f'"{path}" is the current directory.')

    def handle_cwd(self, args):
        if not self._require_login():
            return

        path = self._parse_path(args)
        if path is None:
            return

        try:
            self.session.fs.cwd(path)
            self._send_response(ReplyCode.FileActionOK, "Directory changed.")
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
        except ValueError:
            self._send_response(ReplyCode.ActionNotTakenFilenameNotAllowed)

    def handle_cdup(self, _args):
        if not self._require_login():
            return

        self.session.fs.cdup()
        self._send_response(ReplyCode.FileActionOK, "Directory changed.")

    def handle_mkd(self, args):
        if not self._require_login():
            return

        dirname = self._parse_path(args)
        if dirname is None:
            return

        try:
            created = self.session.fs.mkdir(dirname)
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
            self.session.fs.rmdir(dirname)
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
            listing = self.session.fs.format_list(path or None)
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
            listing = self.session.fs.format_nlst(path or None)
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
                    f" Current directory: {self.session.fs.display_path()}\n"
                    f" Transfer type: {transfer}\n"
                )
                self._send_response(ReplyCode.SystemStatus, info)
                return

            target = self.session.fs.resolve_path(path)
            if os.path.isdir(target):
                info = self.session.fs.format_directory_stat(path)
                self._send_response(ReplyCode.DirectoryStatus, info)
            elif os.path.isfile(target):
                info = self.session.fs.format_file_stat(path)
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
            size = self.session.fs.file_size(filename)
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
            mtime = self.session.fs.file_mtime(filename)
            self._send_response(ReplyCode.FileStatus, mtime)
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)

    def handle_appe(self, line):
        if not self._require_login():
            return
        if not self._require_data_connection():
            return 
        
        filename = self._parse_path(line)
        if filename is None:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return
        try:
            self._send_response(ReplyCode.OpeningData)
            self.session.data_channel.establish()
            
            file_data = self.session.data_channel.recv_file()
            decoded_data = TransferEngine.decode_data(file_data, self.session.mode)
            self.session.fs.append_file(filename, decoded_data)
            self._send_response(ReplyCode.ClosingData, "Transfer complete and file appended.")
        except Exception as e:
            print(f"[APPE] File receiving error: {e}")
            self._send_response(ReplyCode.ConnectionClosed, "Transfer aborted.")
        finally:
            self.session.close_data_channel()

    
    def handle_dele(self, args):
        if not self._require_login():
            return

        filename = self._parse_path(args)
        if filename is None:
            return

        try:
            self.session.fs.delete_file(filename)
            self._send_response(ReplyCode.FileActionOK, "File deleted.")
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)

    def handle_rnfr(self, args):
        if not self._require_login():
            return

        old_name = self._parse_path(args)
        if old_name is None:
            return

        if not self.session.fs.path_exists(old_name):
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
            self.session.fs.rename(self.session.rename_from, new_name)
            self.session.rename_from = None
            self._send_response(ReplyCode.FileActionOK, "Rename complete.")
        except FileNotFoundError:
            self.session.rename_from = None
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable)
        except ValueError:
            self.session.rename_from = None
            self._send_response(ReplyCode.ActionNotTakenFilenameNotAllowed)
            
    def handle_hash(self, line):
        if not self._require_login():
            return
        filename = self._parse_path(line)
        if filename is None:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return 
        try:
            file_hash = self.session.fs.hash_file(filename)
            self._send_response(ReplyCode.FileStatus, f"SHA256 {file_hash}")
        except FileNotFoundError:
            self._send_response(ReplyCode.ActionNotTakenFileUnavailable, "File not found.")

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
        
    def handle_mode(self, line):
        if not self._require_login():
            return
        
        mode_char = line.strip().upper()
        try: 
            selected_mode = TransferMode(mode_char)
            self.session.mode = selected_mode
            self._send_response(ReplyCode.CommandOK, f"Mode set to {selected_mode.name.title()}.")
        except ValueError:
            self._send_response(ReplyCode.ArgumentSyntaxError, "MODE must be S, B, or C.")

    def handle_retr(self, line):
        if not self._require_login():
            return
        if not self._require_data_connection():
            return
        
        filename = self._parse_path(line)
        if filename is None:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return
        try:
            payload = self.session.fs.read_file(filename)
            encoded_payload = TransferEngine.encode_data(payload, self.session.mode)
            
            self._send_response(ReplyCode.OpeningData)
            self.session.data_channel.establish()
            self.session.data_channel.send_file(encoded_payload)
            self._send_response(ReplyCode.ClosingData)
        
        except FileNotFoundError:
            self._send_response(
                ReplyCode.ActionNotTakenFileUnavailable, 
                "File not found."
            )
        except Exception as e:
            print(f"[RETR] File transfer error: {e}")
            self._send_response(ReplyCode.ConnectionClosed, "Transfer aborted.")
        finally:
            self.session.close_data_channel()


    def handle_stor(self, line):
        if not self._require_login():
            return
        if not self._require_data_connection():
            return
        filename = self._parse_path(line)
        if filename is None:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return
        try:
            self._send_response(ReplyCode.OpeningData)
            self.session.data_channel.establish()

            file_data = self.session.data_channel.recv_file()
            decoded_data = TransferEngine.decode_data(file_data, self.session.mode)
            self.session.fs.write_file(filename, decoded_data)
            self._send_response(ReplyCode.ClosingData, "Transfer complete and file saved.")

        except Exception as e:
            print(f"[STOR] File receiving error: {e}")
            self._send_response(ReplyCode.ConnectionClosed, "Transfer aborted.")
        finally:
            try:
                self.session.data_channel.sock.settimeout(None)
            except:
                pass
            self.session.close_data_channel()
            
    def handle_stou(self, line):
        if not self._require_login():
            return
        if not self._require_data_connection():
            return
        
        if line:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return

        try:
            unique_name = self.session.fs.generate_unique_name()
            self._send_response(ReplyCode.OpeningData, f"FILE: {unique_name}")
            self.session.data_channel.establish()

            file_data = self.session.data_channel.recv_file()
            decoded_data = TransferEngine.decode_data(file_data, self.session.mode)
            self.session.fs.write_file(unique_name, decoded_data)
            self._send_response(ReplyCode.ClosingData, f"Transfer complete. Stored as {unique_name}.")

        except Exception as e:
            print(f"[STOU] File receiving error: {e}")
            self._send_response(ReplyCode.ConnectionClosed, "Transfer aborted.")
        finally:
            self.session.close_data_channel()
            
    def handle_port(self, line):
        if not self._require_login():
            return
        print(line)
        self.session.close_data_channel()
        args = line.strip().split(',')
        if len(args) != 6:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return
        
        try:
            host = ".".join(args[:4])
            port = int(args[4])*256 + int(args[5])
            
            self.session.close_data_channel()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("", 0))
            
            self.session.data_channel = ActiveDataChannel(sock, host, port)
            
            self._send_response(ReplyCode.CommandOK)
            
        except (ValueError, OSError):
            self._send_response(
                ReplyCode.CantOpenData,
                "Invalid PORT command."
            )
    
    def handle_pasv(self, line):
        if not self._require_login():
            return
        if line:
            self._send_response(ReplyCode.CommandSyntaxError)
            return
        try:
            self.session.close_data_channel()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("", 0))
            
            host =  self.sock.getsockname()[0]
            _, port = sock.getsockname()
            
            self.session.data_channel = PassiveDataChannel(sock)
            
            h1, h2, h3, h4 = host.split('.')
            p1 = port // 256
            p2 = port % 256
            
            self._send_response(
                ReplyCode.EnteringPassive,
                f"Entering Passive Mode ({h1},{h2},{h3},{h4},{p1},{p2})."
            )
            
        except OSError:
            self._send_response(
                ReplyCode.CantOpenData
            )
            
    def handle_abor(self, line):
        if not self._require_login():
            return
        self._send_response(ReplyCode.ClosingData, "Abort successful.")
        

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


if __name__ == "__main__":
    print(MAX_PAYLOAD)