from .control import ControlChannel
from .data import DataChannel

class FTPServer:
    def __init__(self):
        self.data = DataChannel()
        self.control = ControlChannel(data_channel=self.data)
        
    def start(self):
        pass