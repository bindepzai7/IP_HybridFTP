import socket

from .reply_code import ReplyCode
from .session import Session

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
        
    def process_command(self, line):
        pass
    
    def send_response(self, code, custom_msg):
        pass
    
    def handle_user(self, args): 
        pass
    def handle_pass(self, args): 
        pass
    def handle_quit(self, args): 
        pass
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