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

import threading
import time
import wave

import pyaudio

CHUNK_SIZE = 4096


class Player():
    def __init__(self, pa):
        self.pa = pa
        self.event = threading.Event()
        # self.stream = self.pa.open(format=pyaudio.paInt16,
        #                            channels=1,
        #                            rate=16000,
        #                            output=True,
        #                            start=False,
        #                            # output_device_index=1,
        #                            frames_per_buffer=CHUNK_SIZE,
        #                            stream_callback=self.callback)

    def play(self, wav_file, block=True):
        self.wav = wave.open(wav_file, 'rb')
        self.event.clear()
        self.stream = self.pa.open(format=self.pa.get_format_from_width(self.wav.getsampwidth()),
                                   channels=self.wav.getnchannels(),
                                   rate=self.wav.getframerate(),
                                   output=True,
                                   # output_device_index=1,
                                   frames_per_buffer=CHUNK_SIZE,
                                   stream_callback=self.wav_callback)
        if block:
            self.event.wait()
            time.sleep(2)             # wait for playing audio data in buffer, a alsa driver bug
            self.stream.close()

    def play_raw(self, raw_data, rate=16000, channels=1, width=2, block=True):
        self.raw = raw_data
        self.width = width
        self.channels = channels
        self.event.clear()
        self.stream = self.pa.open(format=self.pa.get_format_from_width(width),
                                   channels=channels,
                                   rate=rate,
                                   output=True,
                                   # output_device_index=1,
                                   frames_per_buffer=CHUNK_SIZE,
                                   stream_callback=self.raw_callback)
        if block:
            self.event.wait()
            time.sleep(2)             # wait for playing audio data in buffer, a alsa driver bug
            self.stream.close()

    def wav_callback(self, in_data, frame_count, time_info, status):
        data = self.wav.readframes(frame_count)
        flag = pyaudio.paContinue
        if self.wav.getnframes() == self.wav.tell():
            data = data.ljust(frame_count * self.wav.getsampwidth() * self.wav.getnchannels(), '\x00')
            # flag = pyaudio.paComplete
            self.event.set()

        return data, flag

    def raw_callback(self, in_data, frame_count, time_info, status):
        size = frame_count * self.width * self.channels
        data = self.raw[:size]
        self.raw = self.raw[size:]
        flag = pyaudio.paContinue
        if not len(self.raw):
            data = data.ljust(frame_count * self.width * self.channels, '\x00')
            # flag = pyaudio.paComplete
            self.event.set()

        return data, flag
