"""
Server-side file system operations.

Handles file and directory management for the FTP server.
"""
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data'))
class FileSystem:
    def __init__(self):
        self.current_directory = ROOT_DIR
    
    def store_file(self, file_path, data):
        with open(file_path, 'wb') as f:
            f.write(data)
    
    def retrieve_file(self, file_path):
        with open(file_path, 'rb') as f:
            return f.read()
