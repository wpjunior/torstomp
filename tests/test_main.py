# -*- coding: utf-8 -*-

from torstomp import TorStomp
from torstomp.subscription import Subscription
from torstomp.frame import Frame

from tornado.testing import AsyncTestCase, gen_test
from tornado import gen
from tornado.iostream import StreamClosedError

from mock import MagicMock


class TestTorStomp(AsyncTestCase):

    def setUp(self):
        super(TestTorStomp, self).setUp()
        self.stomp = TorStomp()

    def test_accept_version_header(self):
        self.assertEqual(self.stomp._connect_headers['accept-version'], '1.1')

    @gen_test
    def test_connect_write_subscriptions(self):
        callback = MagicMock()

        self.stomp._build_io_stream = MagicMock()

        io_stream = MagicMock()

        # mock write operation
        write_future = gen.Future()
        write_future.set_result(None)
        io_stream.write.return_value = write_future

        # mock connect operation
        connect_future = gen.Future()
        connect_future.set_result(None)
        io_stream.connect.return_value = connect_future

        self.stomp._build_io_stream.return_value = io_stream

        self.stomp.subscribe('/topic/test1', ack='client', extra_headers={
            'my-header': 'my-value'
        }, callback=callback)

        yield self.stomp.connect()

        write_calls = self.stomp.stream.write.call_args_list

        self.assertEqual(
            write_calls[0][0][0],
            b'CONNECT\naccept-version:1.1\n\n\x00'
        )

        self.assertEqual(
            write_calls[1][0][0],
            b'SUBSCRIBE\n'
            b'ack:client\ndestination:/topic/test1\n'
            b'id:1\nmy-header:my-value\n\n'
            b'\x00'
        )

    def test_subscribe_create_single_subscription(self):
        callback = MagicMock()

        self.stomp.stream = MagicMock()
        self.stomp.subscribe('/topic/test', ack='client', extra_headers={
            'my-header': 'my-value'
        }, callback=callback)

        subscription = self.stomp._subscriptions['1']

        self.assertIsInstance(subscription, Subscription)
        self.assertEqual(subscription.destination, '/topic/test')
        self.assertEqual(subscription.id, 1)
        self.assertEqual(subscription.ack, 'client')
        self.assertEqual(subscription.extra_headers, {'my-header': 'my-value'})
        self.assertEqual(subscription.callback, callback)

    def test_subscribe_create_multiple_subscriptions(self):
        callback1 = MagicMock()
        callback2 = MagicMock()

        self.stomp.stream = MagicMock()
        self.stomp.subscribe('/topic/test1', ack='client', extra_headers={
            'my-header': 'my-value'
        }, callback=callback1)

        self.stomp.subscribe('/topic/test2', callback=callback2)

        subscription = self.stomp._subscriptions['1']

        self.assertIsInstance(subscription, Subscription)
        self.assertEqual(subscription.destination, '/topic/test1')
        self.assertEqual(subscription.id, 1)
        self.assertEqual(subscription.ack, 'client')
        self.assertEqual(subscription.extra_headers, {'my-header': 'my-value'})
        self.assertEqual(subscription.callback, callback1)

        subscription = self.stomp._subscriptions['2']

        self.assertIsInstance(subscription, Subscription)
        self.assertEqual(subscription.destination, '/topic/test2')
        self.assertEqual(subscription.id, 2)
        self.assertEqual(subscription.ack, 'auto')
        self.assertEqual(subscription.extra_headers, {})
        self.assertEqual(subscription.callback, callback2)

    def test_subscribe_when_connected_write_in_stream(self):
        callback = MagicMock()

        self.stomp.stream = MagicMock()
        self.stomp.connected = True  # fake connected
        self.stomp.subscribe('/topic/test', ack='client', extra_headers={
            'my-header': 'my-value'
        }, callback=callback)

        self.assertEqual(self.stomp.stream.write.call_count, 1)
        self.assertEqual(
            self.stomp.stream.write.call_args[0][0],
            b'SUBSCRIBE\n'
            b'ack:client\n'
            b'destination:/topic/test\n'
            b'id:1\n'
            b'my-header:my-value\n\n\x00')

    def test_subscribe_when_not_connected_write_in_stream(self):
        callback = MagicMock()

        self.stomp.stream = MagicMock()
        self.stomp.connected = False
        self.stomp.subscribe('/topic/test', ack='client', extra_headers={
            'my-header': 'my-value'
        }, callback=callback)

        self.assertEqual(self.stomp.stream.write.call_count, 0)

    def test_send_write_in_stream(self):
        self.stomp.stream = MagicMock()
        self.stomp.send('/topic/test', headers={
            'my-header': 'my-value'
        }, body='{}')

        self.assertEqual(self.stomp.stream.write.call_count, 1)
        self.assertEqual(
            self.stomp.stream.write.call_args[0][0],
            b'SEND\n'
            b'content-length:2\n'
            b'destination:/topic/test\n'
            b'my-header:my-value\n\n'
            b'{}\x00')

    def test_send_utf8_write_in_stream(self):
        self.stomp.stream = MagicMock()
        self.stomp.send('/topic/test', headers={
            'my-header': 'my-value'
        }, body=u'Wilson Júnior')

        self.assertEqual(self.stomp.stream.write.call_count, 1)
        self.assertEqual(
            self.stomp.stream.write.call_args[0][0],
            b'SEND\ncontent-length:14\ndestination:/topic/test\n'
            b'my-header:my-value\n\nWilson J\xc3\xbanior\x00')

    def test_jms_compatible_send_write_in_stream(self):
        self.stomp.stream = MagicMock()
        self.stomp.send('/topic/test', headers={
            'my-header': 'my-value',
        }, body='{}', send_content_length=False)

        self.assertEqual(self.stomp.stream.write.call_count, 1)
        self.assertEqual(
            self.stomp.stream.write.call_args[0][0],
            b'SEND\n'
            b'destination:/topic/test\n'
            b'my-header:my-value\n\n'
            b'{}\x00')

    def test_set_heart_beat_integration(self):
        self.stomp._set_heart_beat = MagicMock()
        self.stomp._on_data(
            b'CONNECTED\n'
            b'heart-beat:100,100\n\n'
            b'{}\x00')

        self.assertEqual(self.stomp._set_heart_beat.call_args[0][0], 100)

    def test_do_heart_beat(self):
        self.stomp.stream = MagicMock()
        self.stomp._schedule_heart_beat = MagicMock()
        self.stomp._do_heart_beat()

        self.assertEqual(self.stomp.stream.write.call_count, 1)
        self.assertEqual(self.stomp.stream.write.call_args[0][0], b'\n')

        self.assertEqual(self.stomp._schedule_heart_beat.call_count, 1)

    def test_do_heart_beat_with_closed_stream(self):
        self.stomp.stream = MagicMock()
        self.stomp.stream.write.side_effect = StreamClosedError()
        self.stomp._schedule_heart_beat = MagicMock()
        self.stomp._do_heart_beat()

        self.assertEqual(self.stomp.stream.write.call_count, 1)
        self.assertEqual(self.stomp.stream.write.call_args[0][0], b'\n')

        self.assertEqual(self.stomp._schedule_heart_beat.call_count, 1)

    def test_subscription_called(self):
        callback = MagicMock()

        self.stomp.stream = MagicMock()
        self.stomp.subscribe('/topic/test', ack='client', extra_headers={
            'my-header': 'my-value'
        }, callback=callback)

        self.stomp._on_data(
            b'MESSAGE\n'
            b'subscription:1\n'
            b'message-id:007\n'
            b'destination:/topic/test\n'
            b'\n'
            b'blah\x00')

        self.assertEqual(callback.call_count, 1)

        frame = callback.call_args[0][0]
        self.assertIsInstance(frame, Frame)
        self.assertEqual(frame.headers['message-id'], '007')
        self.assertEqual(frame.headers['subscription'], '1')
        self.assertEqual(callback.call_args[0][1], 'blah')

    def test_subscription_called_with_double_line_breaks_on_body(self):
        callback = MagicMock()

        self.stomp.stream = MagicMock()
        self.stomp.subscribe('/topic/test', ack='client', extra_headers={
            'my-header': 'my-value'
        }, callback=callback)

        self.stomp._on_data(
            b'MESSAGE\n'
            b'subscription:1\n'
            b'message-id:007\n'
            b'destination:/topic/test\n'
            b'\n'
            b'blahh-line-a\n\nblahh-line-b\n\nblahh-line-c\x00')

        self.assertEqual(callback.call_count, 1)

        frame = callback.call_args[0][0]
        self.assertIsInstance(frame, Frame)
        self.assertEqual(frame.headers['message-id'], '007')
        self.assertEqual(frame.headers['subscription'], '1')
        self.assertEqual(callback.call_args[0][1], 'blahh-line-a\n\nblahh-line-b\n\nblahh-line-c')

    def test_on_error_called(self):
        self.stomp._on_error = MagicMock()
        self.stomp._on_data(
            b'ERROR\n'
            b'message:Invalid error, blah, blah, blah\n'
            b'\n'
            b'Detail Error: blah, blah, blah\x00')

        self.assertEqual(self.stomp._on_error.call_count, 1)

        error = self.stomp._on_error.call_args[0][0]
        self.assertEqual(error.args[0], 'Invalid error, blah, blah, blah')
        self.assertEqual(error.detail, 'Detail Error: blah, blah, blah')

    def test_on_unhandled_frame(self):
        self.stomp._received_unhandled_frame = MagicMock()

        self.stomp._on_data(
            b'FIGHT\n'
            b'teste:1\n'
            b'\n'
            b'ok\x00')

        self.assertEqual(self.stomp._received_unhandled_frame.call_count, 1)

        frame = self.stomp._received_unhandled_frame.call_args[0][0]
        self.assertEqual(frame.command, 'FIGHT')
        self.assertEqual(frame.headers, {'teste': '1'})
        self.assertEqual(frame.body, 'ok')

    def test_ack(self):
        self.stomp.stream = MagicMock()

        frame = Frame('MESSAGE', {
            'subscription': '123',
            'message-id': '321'
        }, 'blah')

        self.stomp.ack(frame)
        self.assertEqual(self.stomp.stream.write.call_count, 1)
        self.assertEqual(
            self.stomp.stream.write.call_args[0][0],
            b'ACK\n'
            b'message-id:321\n'
            b'subscription:123\n\n'
            b'\x00')

    def test_ack_with_unicode_headers(self):
        self.stomp.stream = MagicMock()

        frame = Frame('MESSAGE', {
            'subscription': u'123',
            'message-id': u'321'
        }, u'blah')

        self.stomp.ack(frame)
        self.assertEqual(self.stomp.stream.write.call_count, 1)
        buf = self.stomp.stream.write.call_args[0][0]
        self.assertIsInstance(buf, bytes)
        self.assertEqual(
            buf,
            b'ACK\n'
            b'message-id:321\n'
            b'subscription:123\n\n'
            b'\x00')

    def test_nack(self):
        self.stomp.stream = MagicMock()

        frame = Frame('MESSAGE', {
            'subscription': '123',
            'message-id': '321'
        }, 'blah')

        self.stomp.nack(frame)
        self.assertEqual(self.stomp.stream.write.call_count, 1)
        buf = self.stomp.stream.write.call_args[0][0]
        self.assertIsInstance(buf, bytes)
        self.assertEqual(
            buf,
            b'NACK\n'
            b'message-id:321\n'
            b'subscription:123\n\n'
            b'\x00')
