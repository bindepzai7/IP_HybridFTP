import uuid
from .filesystem import FileSystem
from ..common.mode import TransferMode

class Session:
    def __init__(self, authenticator):
        self.id = str(uuid.uuid4())
        self.authenticator = authenticator

        self.username = None
        self.logged_in = False

        self.data_channel = None

        self.mode = TransferMode.STREAM
        self.type = "A"
        self.rename_from = None
        
        self.fs = FileSystem()

    def set_user(self, username):
        self.username = username

    def login(self):
        self.logged_in = True

    def logout(self):
        self.username = None
        self.logged_in = False

    def close_data_channel(self):
        if self.data_channel:
            try:
                self.data_channel.close()
            except OSError:
                pass
        self.data_channel = None
