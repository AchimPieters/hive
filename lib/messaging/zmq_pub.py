from threading import Lock

import zmq


_INSTANCE_LOCK = Lock()
_INSTANCE = None


class ZmqPublisher:
    def __init__(self):
        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind('tcp://0.0.0.0:10001')

    @classmethod
    def get_instance(cls):
        global _INSTANCE
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = cls()
            return _INSTANCE

    def send_to_ws_server(self, msg):
        self.socket.send(f'ws_server {msg}'.encode('utf-8'))

    def send_to_viewer(self, msg):
        self.socket.send_string(f'viewer {msg}')
