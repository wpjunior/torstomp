# -*- coding: utf-8 -*-

import logging

from tornado import gen
from tornado.ioloop import IOLoop

from torstomp import TorStomp

def on_message(frame, message):
    print(message)

logging.basicConfig(
    format="%(asctime)s - %(filename)s:%(lineno)d - "
    "%(levelname)s - %(message)s",
    level='DEBUG')


def report_error(error):
    print('report_error', error)

@gen.coroutine
def run():
    client = TorStomp('localhost', 61613, connect_headers={
        'heart-beat': '1000,1000'
    }, on_error=report_error)
    client.subscribe('/queue/corumba', callback=on_message)

    yield client.connect()

    client.send('/queue/corumba', body=u'Wilson Júnior', headers={})


def main():
    run()

main()
IOLoop.current().start()
