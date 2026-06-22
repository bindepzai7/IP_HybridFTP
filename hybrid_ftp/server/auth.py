import os
import json
import hashlib

class Authenticator:
    USER_FILE = "../data/users.json"
    
    def __init__(self):
        os.makedirs("../data", exist_ok=True)

        if not os.path.exists(self.USER_FILE):
            with open(self.USER_FILE, "w") as f:
                json.dump({"users": {}}, f, indent=4)
        
    def _load_users(self):
        with open(self.USER_FILE, "r") as  f:
            return json.load(f)
        
    def _save_users(self, data):
        with open(self.USER_FILE, "w") as  f:
            json.dump(data, f, indent=4)
        
    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def user_exists(self, username):
        data = self._load_users()
        return username in data["users"]
        
    def add_user(self, username, password):
        data = self._load_users()
        
        if username in data["users"]:
            return False
        
        data["users"][username] = {
            "password_hash": self._hash_password(password)
        }
        
        self._save_users(data)
        return True
        
    def remove_user(self, username):
        data = self._load_users()
        
        if username not in data["users"]:
            return False
        del data["users"][username]
        
        self._save_users(data)
        return True
        
    def authenticate(self, username, password):
        data = self._load_users()

        user = data["users"].get(username)
        if not user:
            return False

        return user["password_hash"] == self._hash_password(password)
           
        
if __name__ == "__main__":
    authenticator = Authenticator()
    authenticator.add_user("Tuan", "123")
    print(authenticator.user_exists("Tuan"))
    print(authenticator.authenticate("Tuan", "123"))
    authenticator.remove_user("Tuan")
    print(authenticator.user_exists("Tuan"))