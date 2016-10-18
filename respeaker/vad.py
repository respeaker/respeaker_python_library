import collections
import sys

import webrtcvad


class WebRTCVAD:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate

        self.frame_ms = 30
        self.frame_bytes = 2 * self.frame_ms * self.sample_rate / 1000   # S16_LE, 2 bytes width

        self.vad = webrtcvad.Vad(3)
        self.active = False
        self.data = ''
        self.history = collections.deque(maxlen=128)

    def is_speech(self, data):
        self.data += data
        while len(self.data) >= self.frame_bytes:
            frame = self.data[:self.frame_bytes]
            self.data = self.data[self.frame_bytes:]

            if self.vad.is_speech(frame, self.sample_rate):
                sys.stdout.write('1')
                self.history.append(1)
            else:
                sys.stdout.write('0')
                self.history.append(0)

            num_voiced = 0
            for i in range(-8, 0):
                try:
                    num_voiced += self.history[i]
                except IndexError:
                    continue

            if not self.active:
                if num_voiced >= 4:
                    sys.stdout.write('+')
                    self.active = True
                    break
                elif len(self.history) == self.history.maxlen and sum(self.history) == 0:
                    sys.stdout.write('Todo: increase capture volume')
                    for _ in range(self.history.maxlen / 2):
                        self.history.popleft()

            else:
                if num_voiced < 1:
                    sys.stdout.write('-')
                    self.active = False
                elif sum(self.history) > self.history.maxlen * 0.9:
                    sys.stdout.write('Todo: decrease capture volume')
                    for _ in range(self.history.maxlen / 2):
                        self.history.popleft()

        return self.active

    def reset(self):
        self.data = ''
        self.active = False
        self.history.clear()


vad = WebRTCVAD()

