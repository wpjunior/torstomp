# -*- coding:utf-8 -*-
import socket
import logging
import datetime

from tornado.iostream import IOStream
from tornado.ioloop import IOLoop
from tornado import gen

from datetime import timedelta

from torstomp.protocol import StompProtocol
from torstomp.errors import StompError
from torstomp.subscription import Subscription


class TorStomp(object):

    VERSION = '1.1'

    def __init__(self, host='localhost', port=61613, connect_headers={},
                 on_error=None, on_disconnect=None, on_connect=None,
                 reconnect_max_attempts=-1, reconnect_timeout=1000,
                 log_name='TorStomp'):

        self.host = host
        self.port = port
        self.logger = logging.getLogger(log_name)

        self._connect_headers = connect_headers
        self._connect_headers['accept-version'] = self.VERSION
        self._heart_beat_handler = None
        self.connected = False
        self.disconnected_date = None
        self._disconnecting = False
        self._protocol = StompProtocol(log_name=log_name)
        self._subscriptions = {}
        self._last_subscribe_id = 0
        self._on_error = on_error
        self._on_disconnect = on_disconnect
        self._on_connect = on_connect

        self._reconnect_max_attempts = reconnect_max_attempts
        self._reconnect_timeout = timedelta(milliseconds=reconnect_timeout)
        self._reconnect_attempts = 0

    @gen.coroutine
    def connect(self):
        self.stream = self._build_io_stream()

        try:
            yield self.stream.connect((self.host, self.port))
            self.logger.info('Stomp connection estabilished')
        except socket.error as error:
            self.logger.error(
                '[attempt: %d] Connect error: %s', self._reconnect_attempts,
                error)
            self._schedule_reconnect()
            return

        self.stream.set_close_callback(self._on_disconnect_socket)
        self.stream.read_until_close(
            streaming_callback=self._on_data,
            callback=self._on_data)

        self.connected = True
        self._disconnecting = False
        self._reconnect_attempts = 0
        self._protocol.reset()

        yield self._send_frame('CONNECT', self._connect_headers)

        for subscription in self._subscriptions.values():
            yield self._send_subscribe_frame(subscription)

        if self._on_connect:
            self._on_connect()

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

        if self.connected:
            self._send_subscribe_frame(subscription)

    def send(self, destination, body='', headers={}, send_content_length=True):
        headers['destination'] = destination

        if body:
            body = self._protocol._encode(body)

            # ActiveMQ determines the type of a message by the
            # inclusion of the content-length header
            if send_content_length:
                headers['content-length'] = len(body)

        return self._send_frame('SEND', headers, body)

    def ack(self, frame):
        headers = {
            'subscription': frame.headers['subscription'],
            'message-id': frame.headers['message-id']
        }

        return self._send_frame('ACK', headers)

    def nack(self, frame):
        headers = {
            'subscription': frame.headers['subscription'],
            'message-id': frame.headers['message-id']
        }

        return self._send_frame('NACK', headers)

    def _build_io_stream(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        return IOStream(s)

    def _on_disconnect_socket(self):
        self._stop_scheduled_heart_beat()
        self.connected = False
        self.disconnected_date = datetime.datetime.now()

        if self._disconnecting:
            self.logger.info('TCP connection end gracefully')
        else:
            self.logger.info('TCP connection unexpected end')
            self._schedule_reconnect()

        if self._on_disconnect:
            self._on_disconnect()

    def _schedule_reconnect(self):
        if self._reconnect_max_attempts == -1 or \
                self._reconnect_attempts < self._reconnect_max_attempts:

            self._reconnect_attempts += 1
            self._reconnect_timeout_handler = IOLoop.current().add_timeout(
                self._reconnect_timeout, self.connect)
        else:
            self.logger.error('All Connection attempts failed')

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
        self._stop_scheduled_heart_beat()

        self._do_heart_beat()

    def _schedule_heart_beat(self):
        self._heart_beat_handler = IOLoop.current().add_timeout(
            self._heart_beat_delta, self._do_heart_beat)

    def _stop_scheduled_heart_beat(self):
        if self._heart_beat_handler:
            IOLoop.current().remove_timeout(self._heart_beat_handler)

        self._heart_beat_handler = None

    def _do_heart_beat(self):
        self.logger.debug('Sending heartbeat')
        self.stream.write(self._protocol.HEART_BEAT)
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

        subscription.callback(frame, frame.body)

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

        return self._send_frame('SUBSCRIBE', headers)
