ReSpeaker Python Library
========================

[![Build Status](https://travis-ci.org/respeaker/respeaker_python_library.svg?branch=master)](https://travis-ci.org/respeaker/respeaker_python_library)

[ReSpeaker](http://respeaker.io) is an open project to create voice enabled objects.
ReSpeaker python library is an open source python library to provide basic functions of voice interaction.

It uses [PocketSphinx](https://github.com/cmusphinx/pocketsphinx) for keyword spotting and uses [webrtcvad](https://github.com/wiseman/py-webrtcvad) for voice activity detecting.


### Installation
`python` and `pip` are required.

1. Install pocketsphinx, webrtcvad

  On windows, we can use pre-compiled python wheel packages of pocketsphinx and pyaudio from [speech_recognition](https://github.com/Uberi/speech_recognition/tree/master/third-party). For python 2.7, run:
  ```
  pip install https://github.com/respeaker/respeaker_python_library/releases/download/v0.4.1/pocketsphinx-0.0.9-cp27-cp27m-win32.whl
  pip install https://github.com/respeaker/respeaker_python_library/releases/download/v0.4.1/webrtcvad-2.0.9.dev0-cp27-cp27m-win32.whl
  ```

  On Linux
  ```
  pip install pocketsphinx webrtcvad
  ```


2. `pip install pyaudio respeaker --upgrade`



### Getting started

```
import logging
import time
from threading import Thread, Event

import fix_import
from respeaker import Microphone


def task(quit_event):
    mic = Microphone(quit_event=quit_event)

    while not quit_event.is_set():
        if mic.wakeup('respeaker'):
            print('Wake up')
            data = mic.listen()
            text = mic.recognize(data)
            if text:
                print('Recognized %s' % text)


def main():
    logging.basicConfig(level=logging.DEBUG)

    quit_event = Event()
    thread = Thread(target=task, args=(quit_event,))
    thread.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print('Quit')
            quit_event.set()
            break
    thread.join()

if __name__ == '__main__':
    main()
```
