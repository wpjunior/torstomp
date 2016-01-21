# Torstomp
Simple tornado stomp 1.1 client.

## Install 

with pip:

```bash
pip install torstomp
```
## Usage
```python
# -*- coding: utf-8 -*-

from tornado import gen
from tornado.ioloop import IOLoop
from torstomp import TorStomp


@gen.coroutine
def main():
    client = TorStomp('localhost', 61613, connect_headers={
        'heart-beat': '1000,1000'
    }, on_error=report_error)
    client.subscribe('/queue/channel', callback=on_message)

    yield client.connect()

    client.send('/queue/channel', body=u'Thanks', headers={})


def on_message(frame, message):
    print('on_message:', message)

    
def report_error(error):
    print('report_error:', error)


if __name__ == '__main__':
    main()
    IOLoop.current().start()
```

## Contributing
Fork, patch, test, and send a pull request.
