class Frame(object):

    def __init__(self, command, headers, body):
        self.command = command
        self.headers = headers
        self.body = body

    def __repr__(self):
        return '<Frame: %s>' % self.command
