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


import os
import wave
import types
import Queue
import collections
import random
import string
import logging
from threading import Thread, Event

import pyaudio

from pixel_ring import pixel_ring
from vad import vad


logger = logger = logging.getLogger('mic')


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

    logger.info('Save audio as %s' % filename)


class Microphone:
    sample_rate = 16000
    frames_per_buffer = 512
    listening_mask = (1 << 0)
    detecting_mask = (1 << 1)
    recording_mask = (1 << 2)

    def __init__(self, pyaudio_instance=None, quit_event=None):
        pixel_ring.set_color(rgb=0x400000)
    
        self.pyaudio_instance = pyaudio_instance if pyaudio_instance else pyaudio.PyAudio()

        self.device_index = 0
        for i in range(self.pyaudio_instance.get_device_count()):
                dev = self.pyaudio_instance.get_device_info_by_index(i)
                name = dev['name'].encode('utf-8')
                # print(i, name, dev['maxInputChannels'], dev['maxOutputChannels'])
                if name.lower().find('respeaker') >= 0 and dev['maxInputChannels'] > 0:
                    logger.info('Use {}'.format(name))
                    self.device_index = i
                    break

        self.stream = self.pyaudio_instance.open(
            input=True,
            start=False,
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            frames_per_buffer=self.frames_per_buffer,
            stream_callback=self._callback,
            input_device_index=self.device_index,
        )

        self.quit_event = quit_event if quit_event else Event()

        self.listen_queue = Queue.Queue()
        self.detect_queue = Queue.Queue()

        self.decoder = self.create_decoder()
        self.decoder.start_utt()

        self.status = 0
        self.active = False

        self.listen_history = collections.deque(maxlen=8)
        self.detect_history = collections.deque(maxlen=48)

        self.wav = None
        self.record_countdown = None
        self.listen_countdown = [0, 0]

    @staticmethod
    def create_decoder():
        from pocketsphinx.pocketsphinx import Decoder

        path = os.path.dirname(os.path.realpath(__file__))
        pocketsphinx_data = os.getenv('POCKETSPHINX_DATA', os.path.join(path, 'pocketsphinx-data'))
        hmm = os.getenv('POCKETSPHINX_HMM', os.path.join(pocketsphinx_data, 'hmm'))
        dict = os.getenv('POCKETSPHINX_DIC', os.path.join(pocketsphinx_data, 'dictionary.txt'))
        kws = os.getenv('POCKETSPHINX_KWS', os.path.join(pocketsphinx_data, 'keywords.txt'))

        config = Decoder.default_config()
        config.set_string('-hmm', hmm)
        config.set_string('-dict', dict)
        config.set_string('-kws', kws)
        # config.set_int('-samprate', SAMPLE_RATE) # uncomment if rate is not 16000. use config.set_float() on ubuntu
        config.set_int('-nfft', 512)
        config.set_float('-vad_threshold', 2.7)
        config.set_string('-logfn', os.devnull)

        return Decoder(config)

    def recognize(self, data):
        self.decoder.end_utt()
        self.decoder.start_utt()

        if not data:
            return ''

        if isinstance(data, types.GeneratorType):
            for d in data:
                self.decoder.process_raw(d, False, False)
        else:
            self.decoder.process_raw(data, False, True)

        hypothesis = self.decoder.hyp()
        if hypothesis:
            logger.info('Recognized {}'.format(hypothesis.hypstr))
            return hypothesis.hypstr

        return ''

    def detect(self, keyword=None):
        self.decoder.end_utt()
        self.decoder.start_utt()

        pixel_ring.off()

        self.detect_history.clear()

        self.detect_queue.queue.clear()
        self.status |= self.detecting_mask
        self.stream.start_stream()

        result = None
        logger.info('Start detecting')
        while not self.quit_event.is_set():
            size = self.detect_queue.qsize()
            if size > 4:
                logger.info('Too many delays, {} in queue'.format(size))

            data = self.detect_queue.get()
            self.detect_history.append(data)
            self.decoder.process_raw(data, False, False)

            hypothesis = self.decoder.hyp()
            if hypothesis:
                logger.info('Detected {}'.format(hypothesis.hypstr))
                save_as_wav(b''.join(self.detect_history), hypothesis.hypstr)
                self.detect_history.clear()
                if keyword:
                    if hypothesis.hypstr.find(keyword) >= 0:
                        result = hypothesis.hypstr
                        break
                    else:
                        self.decoder.end_utt()
                        self.decoder.start_utt()
                        self.detect_history.clear()
                else:
                    result = hypothesis.hypstr
                    break

        self.status &= ~self.detecting_mask
        self.stop()

        return result

    wakeup = detect

    def listen(self, duration=9, timeout=3):
        vad.reset()

        self.listen_countdown[0] = (duration * self.sample_rate + self.frames_per_buffer - 1) / self.frames_per_buffer
        self.listen_countdown[1] = (timeout * self.sample_rate + self.frames_per_buffer - 1) / self.frames_per_buffer

        self.listen_queue.queue.clear()
        self.status |= self.listening_mask
        self.start()
        pixel_ring.listen()

        logger.info('Start listening')

        def _listen():
            try:
                data = self.listen_queue.get(timeout=timeout)
                while data and not self.quit_event.is_set():
                    yield data
                    data = self.listen_queue.get(timeout=timeout)
            except Queue.Empty:
                pass

            self.stop()

        return _listen()

    def record(self, file_name, seconds=1800):
        self.wav = wave.open(file_name, 'wb')
        self.wav.setsampwidth(2)
        self.wav.setnchannels(1)
        self.wav.setframerate(self.sample_rate)
        self.record_countdown = (seconds * self.sample_rate + self.frames_per_buffer - 1) / self.frames_per_buffer
        self.status |= self.recording_mask
        self.start()

    def quit(self):
        self.status = 0
        self.quit_event.set()
        self.listen_queue.put('')
        if self.wav:
            self.wav.close()
            self.wav = None

    def start(self):
        if self.stream.is_stopped():
            self.stream.start_stream()

    def stop(self):
        if not self.status and self.stream.is_active():
            self.stream.stop_stream()

    def close(self):
        self.quit()
        self.stream.close()

    def _callback(self, in_data, frame_count, time_info, status):
        if self.status & self.recording_mask:
            pass

        if self.status & self.detecting_mask:
            self.detect_queue.put(in_data)

        if self.status & self.listening_mask:
            active = vad.is_speech(in_data)
            if active:
                if not self.active:
                    for d in self.listen_history:
                        self.listen_queue.put(d)
                        self.listen_countdown[0] -= 1

                self.listen_queue.put(in_data)
                self.listen_countdown[0] -= 1
            else:
                if self.active:
                    self.listen_queue.put(in_data)
                else:
                    self.listen_history.append(in_data)

                self.listen_countdown[1] -= 1

            if self.listen_countdown[0] <= 0 or self.listen_countdown[1] <= 0:
                self.listen_queue.put('')
                self.status &= ~self.listening_mask
                pixel_ring.wait()
                logger.info('Stop listening')

            self.active = active

        return None, pyaudio.paContinue


def task(quit_event):
    import time

    mic = Microphone(quit_event=quit_event)

    while not quit_event.is_set():
        if mic.wakeup('respeaker'):
            print('Wake up')
            data = mic.listen()
            text = mic.recognize(data)
            if text:
                time.sleep(3)
                print('Recognized %s' % text)


def main():
    import time

    logging.basicConfig(level=logging.DEBUG)

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
