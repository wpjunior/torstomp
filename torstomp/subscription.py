class Subscription(object):

    def __init__(self, destination, id, ack, extra_headers, callback):
        self.destination = destination
        self.id = id
        self.ack = ack
        self.extra_headers = extra_headers
        self.callback = callback
