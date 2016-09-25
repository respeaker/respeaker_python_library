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
import collections
import os
import sys
import wave
import types
import pyaudio
import webrtcvad
import random
import string
from threading import Thread, Event
from pixel_ring import PixelRing


ACTIVE_CHECK_CHUNKS = [6, 8]  # switch to active state if 8 chunks contains at least 4 active chunks
IDLE_CHECK_CHUNKS = [1, 64]  # switch to idle state if 64 chunks contains less than 2 active chunks

RING_SIZE = 2 ** 7
RING_MASK = RING_SIZE - 1

current_file_dir = os.path.dirname(os.path.realpath(__file__))
pocketsphinx_data = os.getenv('POCKETSPHINX_DATA', os.path.join(current_file_dir, 'pocketsphinx-data'))


def random_string(length):
    return ''.join(random.choice(string.digits) for _ in range(length))


def save_as_wav(data, prefix):
    prefix = prefix.replace(' ', '_')
    filename = prefix + random_string(8) + '.wav'
    while os.path.isfile(filename):
        filename = prefix + random_string(8) + '.wav'

    f = wave.open(filename, 'wb')
    f.setframerate(16000)
    f.setsampwidth(2)
    f.setnchannels(1)
    f.writeframes(data)
    f.close()

    print('Save audio as %s' % filename)


class Microphone:
    sample_rate = 16000
    bytes_30ms = 30 * 2 * sample_rate / 1000  # 30 ms frames bytes

    listening_mask = (1 << 0)
    detecting_mask = (1 << 1)
    recording_mask = (1 << 7)

    def __init__(self, pyaudio_instance=None, quit_event=None, use_pocketsphinx=True):
        self.ring = PixelRing()
        self.ring.set_color(rgb=0x400000)
    
        self.pyaudio_instance = pyaudio_instance if pyaudio_instance else pyaudio.PyAudio()
        self.stream = self.pyaudio_instance.open(
            input=True,
            start=False,
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            frames_per_buffer=2048,
            stream_callback=self._callback,
            # input_device_index=1,
        )

        self.quit_event = quit_event if quit_event else Event()

        self.queue = Queue.Queue()
        self.vad = webrtcvad.Vad(0)

        self.decoder = None
        if use_pocketsphinx:
            self.decoder = self.get_decoder()

        self.status = 0

        self.active = False

        self.data_ring_buffer = collections.deque(maxlen=12)
        self.flag_ring_buffer = bytearray(RING_SIZE)
        self.flag_ring_index = 0

        self.collect_ring_buffer = collections.deque(maxlen=48)

        self.data = ''

        self.wav = None
        self.recording_countdown = None

    @staticmethod
    def create_decoder():
        from pocketsphinx.pocketsphinx import Decoder

        config = Decoder.default_config()
        config.set_string('-hmm', os.path.join(pocketsphinx_data, 'hmm'))
        config.set_string('-dict', os.path.join(pocketsphinx_data, 'dictionary.txt'))
        config.set_string('-kws', os.path.join(pocketsphinx_data, 'keywords.txt'))
        # config.set_int('-samprate', SAMPLE_RATE) # uncomment if rate is not 16000. use config.set_float() on ubuntu
        config.set_int('-nfft', 2048)
        config.set_string('-logfn', os.devnull)

        return Decoder(config)

    def get_decoder(self):
        if not self.decoder:
            self.decoder = self.create_decoder()
            self.decoder.start_utt()
        return self.decoder

    def get_pyaudio(self):
        return self.pyaudio_instance

    def recognize(self, data):
        if not self.decoder:
            self.decoder = self.create_decoder()
            self.decoder.start_utt()
        else:
            self.decoder.end_utt()
            self.decoder.start_utt()

        if not data:
            return ''

        if isinstance(data, types.GeneratorType):
            audio = ''
            for d in data:
                self.decoder.process_raw(d, False, False)
                audio += d
        else:
            self.decoder.process_raw(data, False, True)
            audio = data

        hypothesis = self.decoder.hyp()
        if hypothesis:
            save_as_wav(audio, hypothesis.hypstr)
            print('\nRecognized %s' % hypothesis.hypstr)
            return hypothesis.hypstr

        return ''

    def detect(self, keyword=None):
        self.decoder.end_utt()
        self.decoder.start_utt()

        self.ring.off()

        self.collect_ring_buffer.clear()

        self.queue.queue.clear()
        self.status |= self.listening_mask
        self.stream.start_stream()

        result = None
        while not self.quit_event.is_set():
            data = self.queue.get()
            left = self.queue.qsize()
            if left > 4:
                print('%s chunks delay' % left)

            self.collect_ring_buffer.append(data)

            self.decoder.process_raw(data, False, False)
            hypothesis = self.decoder.hyp()
            if hypothesis:
                print('\nDetected %s' % hypothesis.hypstr)
                save_as_wav(b''.join(self.collect_ring_buffer), hypothesis.hypstr)
                self.collect_ring_buffer.clear()
                if keyword:
                    if hypothesis.hypstr.find(keyword) >= 0:
                        result = True
                        break
                    else:
                        self.decoder.end_utt()
                        self.decoder.start_utt()
                        self.collect_ring_buffer.clear()
                else:
                    result = hypothesis.hypstr
                    break

        self.status &= ~self.listening_mask
        self.stop()

        return result

    wakeup = detect

    def listen(self, duration=9, timeout=6, vad=True):
        self.queue.queue.clear()
        if vad:
            self.data = ''
            self.active = False
            self.data_ring_buffer.clear()
            self.flag_ring_buffer = bytearray(RING_SIZE)
            self.status |= self.detecting_mask
        else:
            self.status |= self.listening_mask
        self.start()
        self.ring.listen()
        return self._listen(duration, timeout)

    def _listen(self, timeout, duration):
        try:
            phrase = 0.0
            data = self.queue.get(timeout=timeout)
            while data and not self.quit_event.is_set():
                yield data
                phrase += len(data) / 2.0 / self.sample_rate
                if phrase >= duration:
                    break
                data = self.queue.get(timeout=timeout)
        except Queue.Empty:
            pass

        self.status &= ~(self.listening_mask & self.detecting_mask)
        self.stop()
        self.ring.wait()

    def record(self, file_name, ms=1800000):
        self.wav = wave.open(file_name, 'wb')
        self.wav.setsampwidth(2)
        self.wav.setnchannels(1)
        self.wav.setframerate(self.sample_rate)
        self.recording_countdown = ms
        self.status |= self.recording_mask
        self.start()

    def quit(self):
        self.status = 0
        self.quit_event.set()
        self.queue.put('')
        if self.wav:
            self.wav.close()
            self.wav = None

    def start(self):
        if self.stream.is_stopped():
            self.stream.start_stream()

    def stop(self):
        if not self.status and self.stream.is_active:
            self.stream.stop_stream()

    def close(self):
        self.quit()
        self.stream.close()

    def _callback(self, in_data, frame_count, time_info, status):
        if self.status & self.recording_mask:
            pass

        if self.status & self.listening_mask:
            self.queue.put(in_data)
        elif self.status & self.detecting_mask:
            self.data += in_data
            while len(self.data) >= self.bytes_30ms:
                data = self.data[:self.bytes_30ms]
                self.data = self.data[self.bytes_30ms:]

                self.data_ring_buffer.append(data)

                active = self.vad.is_speech(data, self.sample_rate)
                sys.stdout.write('1' if active else '0')
                self.flag_ring_buffer[self.flag_ring_index] = 1 if active else 0
                self.flag_ring_index += 1
                self.flag_ring_index &= RING_MASK
                if not self.active:
                    num_voiced = 0
                    for i in range(0, ACTIVE_CHECK_CHUNKS[1]):
                        num_voiced += self.flag_ring_buffer[self.flag_ring_index - i]

                    if num_voiced >= ACTIVE_CHECK_CHUNKS[0]:
                        sys.stdout.write('+')
                        self.active = True
                        self.queue.put(b''.join(self.data_ring_buffer))
                else:
                    num_voiced = 0
                    for i in range(0, IDLE_CHECK_CHUNKS[1]):
                        num_voiced += self.flag_ring_buffer[self.flag_ring_index - i]

                    if num_voiced < IDLE_CHECK_CHUNKS[0]:
                        sys.stdout.write('-')
                        self.queue.put('')
                        self.active = False
                        self.status &= ~self.detecting_mask
                        break
                    else:
                        self.queue.put(data)

                sys.stdout.flush()

        return None, pyaudio.paContinue


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
    import time

    q = Event()
    t = Thread(target=task, args=(q,))
    t.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print('Quit')
            q.set()
            break
    t.join()

if __name__ == '__main__':
    main()
