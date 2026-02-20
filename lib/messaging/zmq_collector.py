from threading import Lock

import json

import zmq

from lib.errors import ZmqCollectorTimeoutError


_INSTANCE_LOCK = Lock()
_INSTANCE = None


class ZmqCollector:
    def __init__(self):
        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.PULL)
        self.socket.bind('tcp://0.0.0.0:5558')
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

    @classmethod
    def get_instance(cls):
        global _INSTANCE
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = cls()
            return _INSTANCE

    def recv_json(self, timeout):
        if self.poller.poll(timeout):
            return json.loads(self.socket.recv(zmq.NOBLOCK))
        raise ZmqCollectorTimeoutError
