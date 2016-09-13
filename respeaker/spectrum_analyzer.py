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

import array
import math
from fft import FFT


class SpectrumAnalyzer:
    def __init__(self, size, sample_rate=16000, band_number=12, window=[50, 8000]):
        self.size = 1 << math.frexp(size - 1)[1]
        self.sample_rate = float(sample_rate)
        self.resolution = self.sample_rate / self.size  # (sample_rate/2) / (band/2)

        self.set_band(band_number, window)

        self.fft = FFT(self.size)

    def set_band(self, n, window=[50, 8000]):
        self.band = n
        self.breakpoints = [0] * (n + 1)
        self.frequencies = [0.0] * (n + 1)
        self.strength = [0.0] * n

        delta = math.pow(float(window[1]) / window[0], 1.0 / n)
        for i in range(n + 1):
            self.frequencies[i] = math.pow(delta, i) * window[0]

        breakpoint = 0
        for i in range(1, self.size / 2):
            if self.resolution * i >= self.frequencies[breakpoint]:
                self.breakpoints[breakpoint] = i
                breakpoint += 1
                if breakpoint > n:
                    break

        self.breakpoints[n] = self.size / 2 + 1
        self.band_size = [self.breakpoints[i + 1] - self.breakpoints[i] for i in range(n)]
        # print self.frequencies
        # print self.breakpoints

    def analyze(self, data):
        amplitude = self.fft.dft(data)
        for i in range(self.band):
            self.strength[i] = sum(amplitude[self.breakpoints[i]:self.breakpoints[i + 1]])  # / self.band_size[i]

        return self.strength


if __name__ == '__main__':
    N = 2048
    rate = 16000

    data = array.array('h', [0] * N)
    w = 2 * math.pi * 50 / rate
    for t in range(N):
        data[t] = int(100 * math.sin(w * t))

    analyzer = SpectrumAnalyzer(N, rate)
    strength = analyzer.analyze(data.tostring())
    print [int(f) for f in analyzer.frequencies]
    print [int(s) for s in strength]
