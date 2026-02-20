import zmq


class ZmqConsumer:
    def __init__(self):
        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.connect('tcp://anthias-server:5558')

    def send(self, msg):
        self.socket.send_json(msg, flags=zmq.NOBLOCK)
