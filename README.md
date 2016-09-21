ReSpeaker Python Library
========================

[ReSpeaker](http://respeaker.io) is an open project to create voice enabled objects.
ReSpeaker python library is an open source python library to provide basic functions of voice interaction.

It uses [PocketSphinx](https://github.com/cmusphinx/pocketsphinx) for keyword spotting and uses [webrtcvad](https://github.com/wiseman/py-webrtcvad) for voice activity detecting.


### Getting started

```
import time
from threading import Thread, Event

import pyaudio
from respeaker import Microphone, Player


mic = None


def task(quit_event):
    global mic

    pa = pyaudio.PyAudio()
    mic = Microphone(pa)
    while not quit_event.is_set():
        if mic.wakeup(keyword='alexa'):
            print('Wake up')
            data = mic.listen()
            text = mic.recognize(data)
            if text.find('play music') >= 0:
                print('Play music')

    mic.close()


def main():
    quit_event = Event()
    thread = Thread(target=task, args=(quit_event,))
    thread.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print('\nquit')
            quit_event.set()
            mic.quit()
            break

    thread.join()


if __name__ == '__main__':
    main()
```