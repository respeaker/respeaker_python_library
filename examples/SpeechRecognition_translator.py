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

import io
import logging
import time
import types
import os

import speech_recognition as sr

from threading import Thread, Event
from respeaker import Microphone
from respeaker.bing_speech_api import BingSpeechAPI


def convert(audio_data):
    if isinstance(audio_data, types.GeneratorType):
        def generate(audio):
            yield BingSpeechAPI.get_wav_header()
            for a in audio:
                yield a
        data = generate(audio_data)
    else:
        data = BingSpeechAPI.to_wav(audio_data)
    audio = sr.AudioData(''.join(data), 16000, 2)
    return audio


def task(quit_event):
    mic = Microphone(quit_event=quit_event)
    r = sr.Recognizer()

    while not quit_event.is_set():
        if mic.wakeup('respeaker'):
            print('Wake up')
            data = mic.listen()
            try:
                text = r.recognize_google(convert(data), language='en-US')
                if text:
                    print('Recognized %s' % text)
            except Exception as e:
                print(e.message)

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
