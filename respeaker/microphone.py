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
from threading import Lock

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


class Microphone:
    def __init__(self, pyaudio_instance, vad_level=3):
        self.pyaudio_instance = pyaudio_instance
        self.stream = self.pyaudio_instance.open(format=pyaudio.paInt16,
                                                 channels=1,
                                                 rate=SAMPLE_RATE,
                                                 input=True,
                                                 start=False,
                                                 input_device_index=1,
                                                 frames_per_buffer=BUFFER_FRAMES,
                                                 stream_callback=self._callback)

        self.queue = Queue.Queue()
        self.lock = Lock()
        self.listening = False
        self.vad = webrtcvad.Vad(vad_level)
        self.decoder = None
        self.decoder_restart = False

        self.recording = False

        self.duration_ms = 0
        self.phrase_ms = 0
        self.max_phrase_ms = 0
        self.max_wait_ms = 0
        self.active = False
        self.padding = 8

        self.ring_buffer = None
        self.ring_buffer_flags = None
        self.ring_buffer_index = 0

        self.wav = None
        self.recording_countdown = None

    @staticmethod
    def _get_decoder():
        from pocketsphinx.pocketsphinx import Decoder

        script_dir = os.path.dirname(os.path.realpath(__file__))
        config = Decoder.default_config()
        config.set_string('-hmm', os.path.join(script_dir, 'pocketsphinx-data/hmm'))
        config.set_string('-dict', os.path.join(script_dir, 'pocketsphinx-data/en.dic'))
        config.set_string('-kws', os.path.join(script_dir, 'pocketsphinx-data/keywords.txt'))
        # config.set_int('-samprate', SAMPLE_RATE) # uncomment if rate is not 16000. use config.set_float() on ubuntu
        config.set_int('-nfft', 2048)
        config.set_string('-logfn', os.devnull)

        return Decoder(config)

    def get_decoder(self):
        if not self.decoder:
            self.decoder = self._get_decoder()

        return self.decoder

    def detect(self, max_phrase_ms=0, max_wait_ms=0, keyword=None):
        if not self.decoder:
            self.decoder = self._get_decoder()
            self.decoder.start_utt()
            self.decoder_restart = False

        chunks = 0
        result = None
        self.listening = True
        self.start(max_phrase_ms, max_wait_ms)
        while self.listening:
            if self.decoder_restart:
                self.decoder.end_utt()  # it takes about 1 second on respeaker
                self.decoder.start_utt()
                self.decoder_restart = False
                chunks = 0

            data, ending = self.queue.get()

            # when self.listening is False, callback function puts an empty data to the queue
            if not data:
                break

            chunks += len(data) / CHUNK_SIZE
            self.decoder.process_raw(data, False, False)
            hypothesis = self.decoder.hyp()
            if hypothesis:
                text = hypothesis.hypstr
                self.decoder_restart = True
                print('\nrecognized %s, analyzed %d chunks' % (text, chunks))
                if keyword:
                    if text.find(keyword) >= 0:
                        result = text
                        break
                else:
                    result = text
                    break

            # ending is True when timeout or get a phrase
            if ending:
                chunks = 0
                if not keyword:
                    break

        self.listening = False
        self.stop()
        return result

    def _listen(self):
        while self.listening:
            data, ending = self.queue.get()
            if not data or ending:
                break
            yield data

        self.listening = False
        self.stop()

    def listen(self, max_phrase_ms=9000, max_wait_ms=4000):
        self.listening = True
        self.start(max_phrase_ms, max_wait_ms)
        return self._listen()

    def record(self, file_name, ms=None):
        self.wav = wave.open(file_name, 'wb')
        self.wav.setsampwidth(2)
        self.wav.setnchannels(1)
        self.wav.setframerate(SAMPLE_RATE)
        self.recording_countdown = ms
        self.recording = True
        if self.stream.is_stopped():
            self.stream.start_stream()

    def interrupt(self, stop_listening=False, stop_recording=False):
        self.listening = not stop_listening
        self.recording = not stop_recording
        if stop_recording:
            if self.wav:
                self.wav.close()
                self.wav = None

    def set_active(self, active=True):
        self.active = active
        if active:
            self.padding = IDLE_CHECK_CHUNKS[1]
            self.ring_buffer_flags = [1] * self.padding
        else:
            self.padding = ACTIVE_CHECK_CHUNKS[1]
            self.ring_buffer_flags = [0] * self.padding

        self.ring_buffer = collections.deque(maxlen=self.padding)
        self.ring_buffer_index = 0

    def start(self, max_phrase_ms=0, max_wait_ms=0):
        self.duration_ms = 0
        self.phrase_ms = 0
        self.max_phrase_ms = max_phrase_ms
        self.max_wait_ms = max_wait_ms
        self.set_active(False)
        self.queue.queue.clear()
        if self.stream.is_stopped():
            self.stream.start_stream()

    def stop(self):
        if self.stream.is_active and not self.recording and not self.listening:
            self.stream.stop_stream()

    def close(self):
        self.interrupt(stop_listening=True, stop_recording=True)
        self.stream.close()

    def _callback(self, in_data, frame_count, time_info, status):
        if self.recording:
            self.wav.writeframes(in_data)
            if self.recording_countdown is not None:
                self.recording_countdown -= BUFFER_MS
                if self.recording_countdown <= 0:
                    self.recording = False
                    self.wav.close()
                    self.stop()

        if self.listening:
            while len(in_data) >= CHUNK_SIZE:
                data = in_data[:CHUNK_SIZE]
                in_data = in_data[CHUNK_SIZE:]

                self.duration_ms += CHUNK_MS
                self.ring_buffer.append(data)

                active = self.vad.is_speech(data, SAMPLE_RATE)
                sys.stdout.write('1' if active else '0')
                self.ring_buffer_flags[self.ring_buffer_index] = 1 if active else 0
                self.ring_buffer_index += 1
                self.ring_buffer_index %= self.padding
                if not self.active:
                    num_voiced = sum(self.ring_buffer_flags)
                    if num_voiced >= ACTIVE_CHECK_CHUNKS[0]:
                        sys.stdout.write('+')
                        self.active = True
                        self.queue.put((b''.join(self.ring_buffer), False))
                        self.phrase_ms = len(self.ring_buffer) * CHUNK_MS
                        self.set_active(True)
                    elif self.max_wait_ms and self.duration_ms > self.max_wait_ms:
                        self.queue.put(('', True))
                else:
                    ending = False  # end of a phrase
                    num_voiced = sum(self.ring_buffer_flags)
                    self.phrase_ms += CHUNK_MS
                    if num_voiced < IDLE_CHECK_CHUNKS[0] or (
                                self.max_phrase_ms and self.phrase_ms >= self.max_phrase_ms):
                        self.set_active(False)
                        ending = True
                        sys.stdout.write('-')

                    self.queue.put((data, ending))

                sys.stdout.flush()
        else:
            self.queue.put(('', True))

        return None, pyaudio.paContinue
