import uuid

class Session:
    def __init__(self, authenticator):
        self.id = str(uuid.uuid4())

        self.authenticator = authenticator

        self.username = None
        self.logged_in = False
        
    def set_user(self, username):
        self.username = username
        
    def login(self):
        self.logged_in = True
        
    def logout(self):
        self.username = None
        self.logged_in = False