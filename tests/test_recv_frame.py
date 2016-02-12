# -*- coding:utf-8 -*-
from unittest import TestCase
import six

from torstomp.protocol import StompProtocol

from mock import MagicMock


class TestRecvFrame(TestCase):

    def setUp(self):
        self.protocol = StompProtocol()

    def test_decode(self):
        self.assertEqual(
            self.protocol._decode(u'éĂ'),
            u'éĂ'
        )

    def test_on_decode_error_show_string(self):
        data = MagicMock(spec=six.binary_type)
        data.decode.side_effect = UnicodeDecodeError(
            'hitchhiker',
            b"",
            42,
            43,
            'the universe and everything else'
        )
        with self.assertRaises(UnicodeDecodeError):
            self.protocol._decode(data)

    def test_single_packet(self):
        self.protocol._proccess_frame = MagicMock()

        self.protocol.add_data(
            'CONNECT\n'
            'accept-version:1.0\n\n\x00'
        )

        self.assertTrue(self.protocol._proccess_frame.called)
        self.assertEqual(self.protocol._proccess_frame.call_count, 1)
        self.assertEqual(
            self.protocol._proccess_frame.call_args[0][0],
            'CONNECT\n'
            'accept-version:1.0\n\n'
        )
        self.assertEqual(self.protocol._pending_parts, [])

    def test_parcial_packet(self):
        self.protocol._proccess_frame = MagicMock()

        self.protocol.add_data(
            'CONNECT\n'
        )

        self.protocol.add_data(
            'accept-version:1.0\n\n\x00'
        )

        self.assertTrue(self.protocol._proccess_frame.called)
        self.assertEqual(self.protocol._proccess_frame.call_count, 1)
        self.assertEqual(
            self.protocol._proccess_frame.call_args[0][0],
            'CONNECT\n'
            'accept-version:1.0\n\n'
        )
        self.assertEqual(self.protocol._pending_parts, [])

    def test_multi_parcial_packet1(self):
        self.protocol._proccess_frame = MagicMock()

        self.protocol.add_data(
            'CONNECT\n'
        )

        self.protocol.add_data(
            'accept-version:1.0\n\n\x00\n'
        )

        self.protocol.add_data(
            'CONNECTED\n'
        )

        self.protocol.add_data(
            'accept-version:1.0\n\n\x00\n'
        )

        self.assertTrue(self.protocol._proccess_frame.called)
        self.assertEqual(self.protocol._proccess_frame.call_count, 2)
        self.assertEqual(
            self.protocol._proccess_frame.call_args_list[0][0][0],
            'CONNECT\n'
            'accept-version:1.0\n\n'
        )

        self.assertEqual(
            self.protocol._proccess_frame.call_args_list[1][0][0],
            'CONNECTED\n'
            'accept-version:1.0\n\n'
        )
        self.assertEqual(self.protocol._pending_parts, [])

    def test_multi_parcial_packet2(self):
        self.protocol._proccess_frame = MagicMock()

        self.protocol.add_data(
            'CONNECTED\n'
            'accept-version:1.0\n\n'
        )

        self.protocol.add_data(
            '\x00\nERROR\n'
        )

        self.protocol.add_data(
            'header:1.0\n\n\x00\n'
        )

        self.assertTrue(self.protocol._proccess_frame.called)
        self.assertEqual(self.protocol._proccess_frame.call_count, 2)
        self.assertEqual(
            self.protocol._proccess_frame.call_args_list[0][0][0],
            'CONNECTED\n'
            'accept-version:1.0\n\n'
        )
        self.assertEqual(self.protocol._pending_parts, [])
        self.assertEqual(
            self.protocol._proccess_frame.call_args_list[1][0][0],
            'ERROR\n'
            'header:1.0\n\n'
        )
        self.assertEqual(self.protocol._pending_parts, [])

    def test_heart_beat_packet1(self):
        self.protocol._proccess_frame = MagicMock()
        self.protocol._recv_heart_beat = MagicMock()
        self.protocol.add_data('\n')
        self.assertFalse(self.protocol._proccess_frame.called)

        self.assertTrue(self.protocol._recv_heart_beat.called)
        self.assertEqual(self.protocol._pending_parts, [])

    def test_heart_beat_packet2(self):
        self.protocol._proccess_frame = MagicMock()
        self.protocol._recv_heart_beat = MagicMock()
        self.protocol.add_data(
            'CONNECT\n'
            'accept-version:1.0\n\n\x00\n'
        )

        self.assertTrue(self.protocol._proccess_frame.called)
        self.assertTrue(self.protocol._recv_heart_beat.called)
        self.assertEqual(self.protocol._pending_parts, [])

    def test_heart_beat_packet3(self):
        self.protocol._proccess_frame = MagicMock()
        self.protocol._recv_heart_beat = MagicMock()
        self.protocol.add_data(
            '\nCONNECT\n'
            'accept-version:1.0\n\n\x00'
        )

        self.assertTrue(self.protocol._proccess_frame.called)
        self.assertTrue(self.protocol._recv_heart_beat.called)
        self.assertEqual(self.protocol._pending_parts, [])


class TestBuildFrame(TestCase):

    def setUp(self):
        self.protocol = StompProtocol()

    def test_build_frame_with_body(self):
        buf = self.protocol.build_frame('HELLO', {
            'from': 'me',
            'to': 'you'
        }, 'I Am The Walrus')

        self.assertEqual(
            buf,
            b'HELLO\n'
            b'from:me\n'
            b'to:you\n\n'
            b'I Am The Walrus'
            b'\x00')

    def test_build_frame_without_body(self):
        buf = self.protocol.build_frame('HI', {
            'from': '1',
            'to': '2'
        })

        self.assertEqual(
            buf,
            b'HI\n'
            b'from:1\n'
            b'to:2\n\n'
            b'\x00')


class TestReadFrame(TestCase):

    def setUp(self):
        self.protocol = StompProtocol()

    def test_single_packet(self):
        self.protocol.add_data(
            'CONNECT\n'
            'accept-version:1.0\n\n\x00'
        )

        self.assertEqual(len(self.protocol._frames_ready), 1)

        frame = self.protocol._frames_ready[0]
        self.assertEqual(frame.command, 'CONNECT')
        self.assertEqual(frame.headers, {'accept-version': '1.0'})
        self.assertEqual(frame.body, None)
