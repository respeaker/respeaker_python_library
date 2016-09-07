"""
 ReSpeaker Python Library
 Copyright (c) 2016 Seeed Technology Limited.

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import time
from threading import Thread, Event

import pyaudio

try:
    from respeaker import *
except ImportError:
    import fix_import
    from respeaker import *


mic = None


def task(quit_event):
    global mic

    pixels = PixelRing()
    pixels.set_color(rgb=0x400000)

    pa = pyaudio.PyAudio()
    mic = Microphone(pa)

    pixels.set_color(rgb=0x004000)
    time.sleep(2)
    pixels.off()

    while not quit_event.is_set():
        if mic.wakeup(keyword='alexa'):
            print('Wake up')
            pixels.listen()

            data = mic.listen()
            text = mic.recognize(data)

            pixels.wait()
            if text.find('play music') >= 0:
                print('Play music')

        pixels.off()

    pixels.off()
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
