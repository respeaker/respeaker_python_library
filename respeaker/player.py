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

import Queue
import audioop
import threading
import types
import wave

import pyaudio

from spectrum_analyzer import SpectrumAnalyzer
from spi import spi

CHUNK_SIZE = 1024
BAND_NUMBER = 16


class Player:
    def __init__(self, pyaudio_instance=None):
        self.pyaudio_instance = pyaudio_instance if pyaudio_instance else pyaudio.PyAudio()
        self.stop_event = threading.Event()

        def ignite(queue):
            data = queue.get()
            analyzer = SpectrumAnalyzer(len(data), band_number=BAND_NUMBER)
            while True:
                while not queue.empty():
                    data = queue.get()

                amplitude = analyzer.analyze(data)
                level = bytearray(len(amplitude))
                for i, v in enumerate(amplitude):
                    l = int(v / 1024 / 128)
                    if l > 255:
                        l = 255
                    level[i] = l

                spi.write(address=0xA0, data=level)

                data = queue.get()

        self.queue = Queue.Queue()
        self.thread = threading.Thread(target=ignite, args=(self.queue,))
        self.thread.daemon = True
        self.thread.start()

    def _play(self, data, rate=16000, channels=1, width=2, spectrum=True):
        stream = self.pyaudio_instance.open(
            format=self.pyaudio_instance.get_format_from_width(width),
            channels=channels,
            rate=rate,
            output=True,
            # output_device_index=1,
            frames_per_buffer=CHUNK_SIZE,
        )

        if isinstance(data, types.GeneratorType):
            for d in data:
                if self.stop_event.is_set():
                    break

                stream.write(d)

                if spectrum:
                    if channels == 2:
                        d = audioop.tomono(d, 2, 0.5, 0.5)
                    self.queue.put(d)
        else:
            stream.write(data)

        stream.close()

    def play(self, wav=None, data=None, rate=16000, channels=1, width=2, block=True, spectrum=None):
        if wav:
            f = wave.open(wav, 'rb')
            rate = f.getframerate()
            channels = f.getnchannels()
            width = f.getsampwidth()

            def gen(w):
                d = w.readframes(CHUNK_SIZE)
                while d:
                    yield d
                    d = w.readframes(CHUNK_SIZE)
                d.close()

            data = gen(f)

        self.stop_event.clear()
        if block:
            self._play(data, rate, channels, width, spectrum)
        else:
            thread = threading.Thread(target=self._play, args=(data, rate, channels, width, spectrum))
            thread.start()

    def play_raw(self, data, rate=16000, channels=1, width=2):
        self.play(data=data, rate=rate, channels=channels, width=width)

    def stop(self):
        self.stop_event.set()


def main():
    import sys

    if len(sys.argv) < 2:
        print('Usage: python {} music.wav'.format(sys.argv[0]))
        sys.exit(1)

    player = Player()
    player.play(sys.argv[1], spectrum=True)


if __name__ == '__main__':
    main()
