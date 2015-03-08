from unittest import TestCase

from torstomp.protocol import StompProtocol

from mock import MagicMock


class TestRecvFrame(TestCase):

    def setUp(self):
        self.protocol = StompProtocol()

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
            'HELLO\n'
            'from:me\n'
            'to:you\n\n'
            'I Am The Walrus'
            '\x00')

    def test_build_frame_without_body(self):
        buf = self.protocol.build_frame('HI', {
            'from': '1',
            'to': '2'
        })

        self.assertEqual(
            buf,
            'HI\n'
            'from:1\n'
            'to:2\n\n'
            '\x00')


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
