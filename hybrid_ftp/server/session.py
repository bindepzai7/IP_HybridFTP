import uuid


class Session:
    def __init__(self, authenticator):
        self.id = str(uuid.uuid4())
        self.authenticator = authenticator

        self.username = None
        self.logged_in = False

        self.data_socket = None
        self.data_port = None
        self.data_host = None

    def set_user(self, username):
        self.username = username

    def login(self):
        self.logged_in = True

    def logout(self):
        self.username = None
        self.logged_in = False

    def close_data_channel(self):
        if self.data_socket:
            try:
                self.data_socket.close()
            except OSError:
                pass
        self.data_socket = None
        self.data_port = None
        self.data_host = None
