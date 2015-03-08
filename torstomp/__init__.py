import socket
import logging

from tornado.iostream import IOStream
from tornado.ioloop import IOLoop
from tornado import gen

from datetime import timedelta
from protocol import StompProtocol
from errors import StompError
from subscription import Subscription


class TorStomp(object):
    VERSION = '1.1'

    def __init__(self, host='localhost', connect_headers={},
                 port=61613, on_error=None):

        self.host = host
        self.port = port
        self.logger = logging.getLogger('TorStomp')

        self._connect_headers = connect_headers
        self._connect_headers['accept-version'] = self.VERSION
        self._heart_beat_handler = None
        self._protocol = StompProtocol()
        self._subscriptions = {}
        self._last_subscribe_id = 0
        self._on_error = on_error

    @gen.coroutine
    def connect(self):
        self.stream = self._build_io_stream()

        try:
            yield self.stream.connect((self.host, self.port))
            self.logger.debug('TCP connection estabilished')
        except socket.error as error:
            self.logger.error('TCP connection connection error: %s', error)
            return

        self.stream.set_close_callback(self._on_disconnect)
        self.stream.read_until_close(
            streaming_callback=self._on_data,
            callback=self._on_data)

        self._connected = True
        self._protocol.reset()

        yield self._send_frame('CONNECT', self._connect_headers)

    def subscribe(self, destination, ack='auto', extra_headers={},
                  callback=None):

        self._last_subscribe_id += 1

        subscription = Subscription(
            destination=destination,
            id=self._last_subscribe_id,
            ack=ack,
            extra_headers=extra_headers,
            callback=callback)

        self._subscriptions[str(self._last_subscribe_id)] = subscription
        self._send_subscribe_frame(subscription)

    def send(self, destination, body='', headers={}):
        headers['destination'] = destination
        headers['content-length'] = len(body)

        return self._send_frame('SEND', headers, body)

    def _build_io_stream(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        return IOStream(s)

    def _on_disconnect(self):
        self.logger.info('TCP connection end')

    def _on_data(self, data):
        if not data:
            return

        self._protocol.add_data(data)

        frames = self._protocol.pop_frames()
        if frames:
            self._received_frames(frames)

    def _send_frame(self, command, headers={}, body=''):
        buf = self._protocol.build_frame(command, headers, body)
        return self.stream.write(buf)

    def _set_connected(self, connected_frame):
        heartbeat = connected_frame.headers.get('heart-beat')

        if heartbeat:
            sx, sy = heartbeat.split(',')
            sx, sy = int(sx), int(sy)

            if sy:
                self._set_heart_beat(sy)

    def _set_heart_beat(self, time):
        self._heart_beat_delta = timedelta(milliseconds=time)
        if self._heart_beat_handler:
            self._heart_beat_handler.remove_timeout()

        self._do_heart_beat()

    def _schedule_heart_beat(self):
        self._heart_beat_handler = IOLoop.current().add_timeout(
            self._heart_beat_delta, self._do_heart_beat)

    def _do_heart_beat(self):
        self.logger.debug('Sending heartbeat')
        self.stream.write('\n')
        self._schedule_heart_beat()

    def _received_frames(self, frames):
        for frame in frames:
            if frame.command == 'MESSAGE':
                self._received_message_frame(frame)
            elif frame.command == 'CONNECTED':
                self._set_connected(frame)
            elif frame.command == 'ERROR':
                self._received_error_frame(frame)
            else:
                self._received_unhandled_frame(frame)

    def _received_message_frame(self, frame):
        subscription_header = frame.headers.get('subscription')

        subscription = self._subscriptions.get(subscription_header)

        if not subscription:
            self.logger.error(
                'Not found subscription %d' % subscription_header)
            return

        message_id = frame.headers.get('message-id')
        subscription.callback(message_id, frame.headers, frame.body)

    def _received_error_frame(self, frame):
        message = frame.headers.get('message')

        self.logger.error('Received error: %s', message)
        self.logger.debug('Error detail %s', frame.body)

        if self._on_error:
            self._on_error(
                StompError(message, frame.body))

    def _received_unhandled_frame(self, frame):
        self.logger.warn('Received unhandled frame: %s', frame.command)

    def _send_subscribe_frame(self, subscription):
        headers = {
            'id': subscription.id,
            'destination': subscription.destination,
            'ack': subscription.ack
        }
        headers.update(subscription.extra_headers)

        self._send_frame('SUBSCRIBE', headers)