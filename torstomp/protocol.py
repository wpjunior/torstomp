import logging
import codecs

from frame import Frame

class StompProtocol(object):
    EOF = b'\x00'

    def __init__(self):
        self._pending_parts = []
        self._frames_ready = []

        self.decoder = codecs.lookup('utf-8')
        self.logger = logging.getLogger('StompProtocol')

    def reset(self):
        self._pending_parts = []
        self._frames_ready = []

    def add_data(self, data):
        if not self._pending_parts:
            if data[0] == '\n':
                self._recv_heart_beat()
                data = data[1:]

                if data:
                    return self.add_data(data)

        parts = data.split(self.EOF, 1)
        len_parts = len(parts)

        if len_parts == 1:
            if data:
                self._pending_parts.append(data)

        elif len_parts > 1:
            if parts[0]:
                self._pending_parts.append(parts[0])

            frame = ''.join(self._pending_parts)
            self._pending_parts = []
            self._proccess_frame(frame)

            if parts[1]:
                self.add_data(parts[1])

    def _proccess_frame(self, data):
        data = self.decoder.decode(data)[0]
        command, remaing = data.split('\n', 1)


        raw_headers, remaing = remaing.split('\n\n')
        headers = dict([l.split(':', 1) for l in raw_headers.split('\n')])
        body = remaing if remaing else None

        self._frames_ready.append(Frame(command, headers=headers, body=body))

    def _recv_heart_beat(self):
        self.logger.debug('Heartbeat received')

    def build_frame(self, command, headers={}, body=''):
        lines = [command, '\n']

        for key, value in sorted(headers.items()):
            lines.append('%s:%s\n' % (key, value))

        lines.append("\n")
        lines.append(body)
        lines.append(self.EOF)

        return ''.join(lines)

    def pop_frames(self):
        frames = self._frames_ready
        self._frames_ready = []

        return frames
