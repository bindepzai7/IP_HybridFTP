from reply_code import ReplyCode, DefaultMessage
from session import Session
from auth import Authenticator

class ControlChannel:
    def __init__(self, client_sock, session):
        self.sock = client_sock
        self.session = session
        
        self.handlers = {
            "USER"  : self.handle_user,
            "PASS"  : self.handle_pass,
            "QUIT"  : self.handle_quit,
            "NOOP"  : self.handle_noop,
            "PWD"   : self.handle_pwd,
            "CWD"   : self.handle_cwd,
            "CDUP"  : self.handle_cdup,
            "MKD"   : self.handle_mkd,
            "RMD"   : self.handle_rmd,
            "LIST"  : self.handle_list,
            "NLST"  : self.handle_nlst,
            "STAT"  : self.handle_stat,
            "SIZE"  : self.handle_size,
            "MDTM"  : self.handle_mdtm,
            "TYPE"  : self.handle_type,
            "MODE"  : self.handle_mode,
            "PORT"  : self.handle_port,
            "PASV"  : self.handle_pasv,
            "RETR"  : self.handle_retr,
            "STOR"  : self.handle_stor,
            "STOU"  : self.handle_stou,
            "APPE"  : self.handle_appe,
            "DELE"  : self.handle_dele,
            "RNFR"  : self.handle_rnfr,
            "RNTO"  : self.handle_rnto,
            "HASH"  : self.handle_hash,
            "ABOR"  : self.handle_abor,
            "HELP"  : self.handle_help,
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

        return handler(arg)
    
    def _send_response(self, code, custom_msg=None):
        if custom_msg is None:
            msg = DefaultMessage[code]
        else:
            msg = custom_msg

        response = f"{int(code)} {msg}\r\n"
        self.sock.sendall(response.encode())
        # print(response)
        
    def run(self):
        self._send_response(ReplyCode.SendUserCommand)

        while True:
            data = self.sock.recv(1024)
            if not data:
                break

            line = data.decode().strip()
            action = self._process_command(line)

            if action == "CLOSE":
                break

        self.sock.close()
    
    def handle_user(self, line):
        username = line.strip()

        if not username:
            self._send_response(ReplyCode.ArgumentSyntaxError)
            return

        if self.session.logged_in:
            self._send_response(
                ReplyCode.BadCommandSequence,
                "Already logged in."
            )
            return

        if not self.session.authenticator.user_exists(username):
            self._send_response(
                ReplyCode.NotLoggedIn,
                "Invalid username."
            )
            return

        self.session.set_user(username)

        self._send_response(
            ReplyCode.SendPasswordCommand
        )
        
    def handle_pass(self, line): 
        password = line.strip()
        if self.session.username is None:
            self._send_response(ReplyCode.BadCommandSequence)
            return None
        
        ok = self.session.authenticator.authenticate(self.session.username, password)
        
        if not ok:
            self._send_response(ReplyCode.NotLoggedIn)
            return None
        
        self.session.login()
        self._send_response(ReplyCode.LoggedInProceed)
        
    def handle_quit(self, line): 
        if line:
            self._send_response(ReplyCode.CommandSyntaxError)
            return 
        
        self.session.logout()
        self._send_response(ReplyCode.ClosingControl)
        return "CLOSE"
        
    def handle_noop(self, args): 
        pass
    def handle_pwd(self, args): 
        pass
    def handle_cwd(self, args): 
        pass
    def handle_cdup(self, args): 
        pass
    def handle_mkd(self, args): 
        pass
    def handle_rmd(self, args): 
        pass
    def handle_list(self, args): 
        pass
    def handle_nlst(self, args): 
        pass
    def handle_stat(self, args): 
        pass
    def handle_size(self, args): 
        pass
    def handle_mdtm(self, args): 
        pass
    def handle_type(self, args): 
        pass
    def handle_mode(self, args): 
        pass
    def handle_port(self, args): 
        pass
    def handle_pasv(self, args): 
        pass
    def handle_retr(self, args): 
        pass
    def handle_stor(self, args): 
        pass
    def handle_stou(self, args): 
        pass
    def handle_appe(self, args): 
        pass
    def handle_dele(self, args): 
        pass
    def handle_rnfr(self, args): 
        pass
    def handle_rnto(self, args): 
        pass
    def handle_hash(self, args): 
        pass
    def handle_abor(self, args): 
        pass
    def handle_help(self, args): 
        pass
    
if __name__ == "__main__":
    auth = Authenticator()
    # auth.add_user("alice", "123")

    session = Session(auth)
    control = ControlChannel(None, session)
    control.handle_user("alice")
    control.handle_pass("123")
    control._process_command("QUIT")