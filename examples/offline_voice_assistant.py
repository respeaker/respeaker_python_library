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

from respeaker import Microphone
from respeaker import Player

mic = None
quit_event = Event()


def main():
    global mic, quit_event

    pa = pyaudio.PyAudio()
    mic = Microphone(pa)
    player = Player(pa)

    while not quit_event.is_set():
        if mic.detect(keyword='hey respeaker'):
            print('wakeup')
            command = mic.detect(max_phrase_ms=6000, max_wait_ms=4000)
            if command:
                print('recognized: ' + command)
                if command.find('play music') > 0:
                    pass

    mic.close()


if __name__ == '__main__':
    thread = Thread(target=main)
    thread.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print('\nquit')
            quit_event.set()
            mic.interrupt(True, True)
            break

    thread.join()
