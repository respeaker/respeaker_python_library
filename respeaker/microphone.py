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

import pyaudio
import webrtcvad

SAMPLE_RATE = 16000
CHUNK_MS = 30  # VAD chunk length: 10, 20 or 30 (ms)
CHUNK_FRAMES = int(SAMPLE_RATE * CHUNK_MS / 1000)  # 30 * 16 = 480
CHUNK_SIZE = CHUNK_FRAMES * 2  # 2 bytes width
BUFFER_FRAMES = CHUNK_FRAMES * 8
BUFFER_MS = BUFFER_FRAMES * CHUNK_MS / CHUNK_FRAMES
ACTIVE_CHECK_CHUNKS = [4, 8]  # switch to active state if 8 chunks contains at least 4 active chunks
IDLE_CHECK_CHUNKS = [2, 48]  # switch to idle state if 64 chunks contains less than 2 active chunks

RING_SIZE = 64
RING_MASK = 63

current_file_dir = os.path.dirname(os.path.realpath(__file__))
pocketsphinx_data = os.getenv('POCKETSPHINX_DATA', os.path.join(current_file_dir, 'pocketsphinx-data'))


class Microphone:
    def __init__(self, pyaudio_instance, vad_level=3, use_pocketsphinx=True):
        self.pyaudio_instance = pyaudio_instance
        self.stream = self.pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            start=False,
            input_device_index=1,
            frames_per_buffer=BUFFER_FRAMES,
            stream_callback=self._callback
        )

        self.queue = Queue.Queue()
        self.vad = webrtcvad.Vad(vad_level)

        self.decoder = None
        if use_pocketsphinx:
            self.decoder = self.get_decoder()

        self.listening = False
        self.recording = False

        self.active = False
        self.padding = 8

        self.data_ring_buffer = collections.deque(maxlen=8)
        self.flag_ring_buffer = bytearray(RING_SIZE)
        self.flag_ring_index = 0

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

    def recognize(self, data):
        if not self.decoder:
            self.decoder = self.create_decoder()
            self.decoder.start_utt()
        else:
            self.decoder.end_utt()
            self.decoder.start_utt()

        if not data:
            return ''

        for d in data:
            self.decoder.process_raw(d, False, False)

        hypothesis = self.decoder.hyp()
        if hypothesis:
            print('\nRecognized %s' % hypothesis.hypstr)
            return hypothesis.hypstr

        return ''

    def wakeup(self, keyword, stop_stream=True):
        if not self.decoder:
            self.decoder = self.create_decoder()
            self.decoder.start_utt()
        else:
            self.decoder.end_utt()
            self.decoder.start_utt()

        result = None
        text = None

        self.listening = True

        self.flag_ring_buffer = bytearray(RING_SIZE)
        self.active = False
        self.start()
        while self.listening:
            data = self.queue.get()
            # sys.stdout.write('  %d  ' % self.queue.qsize())

            # when self.listening is False, callback function puts an empty data to the queue
            if not data:
                break

            self.decoder.process_raw(data, False, False)
            hypothesis = self.decoder.hyp()
            if hypothesis and hypothesis.hypstr != text:
                text = hypothesis.hypstr
                print('\nDetected %s' % text)
                if text.find(keyword) >= 0:
                    result = text
                    break

        if stop_stream:
            self.listening = False
            self.stop()
        else:
            self.flag_ring_buffer = bytearray(RING_SIZE)
            self.active = False

        return result

    def listen(self, timeout=3, max_phrase=9):
        if not self.listening:
            self.queue.queue.clear()
            self.flag_ring_buffer = bytearray(RING_SIZE)
            self.active = False
        self.listening = 1
        self.start()
        return self._listen(timeout, max_phrase)

    def _listen(self, timeout, max_phrase):
        try:
            phrase = 0.0
            data = self.queue.get(timeout=timeout)
            while data:
                yield data
                phrase += len(data) / 2.0 / SAMPLE_RATE
                if phrase >= max_phrase:
                    self.listening = 0
                    self.active = False
                    break
                data = self.queue.get(timeout=timeout)
        except Queue.Empty:
            pass

        self.stop()

    def record(self, file_name, ms=1800000):
        self.wav = wave.open(file_name, 'wb')
        self.wav.setsampwidth(2)
        self.wav.setnchannels(1)
        self.wav.setframerate(SAMPLE_RATE)
        self.recording_countdown = ms
        self.recording = True
        if self.stream.is_stopped():
            self.stream.start_stream()

    def quit(self):
        self.listening = False
        self.recording = False
        self.queue.put('')
        if self.wav:
            self.wav.close()
            self.wav = None

    def start(self):
        if self.stream.is_stopped():
            self.stream.start_stream()

    def stop(self):
        if self.stream.is_active and not (self.recording or self.listening):
            self.stream.stop_stream()

    def close(self):
        self.quit()
        self.stream.close()

    def _callback(self, in_data, frame_count, time_info, status):
        if self.recording:
            self.wav.writeframes(in_data)
            self.recording_countdown -= BUFFER_MS
            if self.recording_countdown <= 0:
                self.recording = False
                self.wav.close()
                self.wav = None

        if self.listening:
            while len(in_data) >= CHUNK_SIZE:
                data = in_data[:CHUNK_SIZE]
                in_data = in_data[CHUNK_SIZE:]

                self.data_ring_buffer.append(data)

                active = self.vad.is_speech(data, SAMPLE_RATE)
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
                        self.active = False
                        if 1 == self.listening:
                            self.listening = 0
                            self.queue.put('')
                            break
                    else:
                        self.queue.put(data)

                sys.stdout.flush()

        return None, pyaudio.paContinue
