"""
 DFT wrapper of FFTW3
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
import ctypes
import math
import os


class FFT:
    def __init__(self, size):
        self.size = 1 << math.frexp(size - 1)[1]

        self.real_input = array.array('f', [0.0] * self.size)
        self.complex_output = array.array('f', [0.0] * (self.size * 2))
        self.amplitude = array.array('f', [0.0] * (self.size / 2 + 1))
        self.phase = array.array('f', [0.0] * (self.size / 2 + 1))

        if os.name == "nt":
            self.fftw3f = ctypes.CDLL('libfftw3f-3.dll')
        else:
            self.fftw3f = ctypes.CDLL('libfftw3f.so')

        # fftw_plan fftw_plan_dft_r2c_1d(int band_number, double *in, fftw_complex *out, unsigned flags);
        self.fftwf_plan_dft_r2c_1d = self.fftw3f.fftwf_plan_dft_r2c_1d
        self.fftwf_plan_dft_r2c_1d.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint)
        self.fftwf_plan_dft_r2c_1d.restype = ctypes.c_void_p

        # void fftwf_execute(const fftwf_plan plan)
        self.fftwf_execute = self.fftw3f.fftwf_execute
        self.fftwf_execute.argtypes = (ctypes.c_void_p,)
        self.fftwf_execute.restype = None

        input_ptr, _ = self.real_input.buffer_info()
        output_ptr, _ = self.complex_output.buffer_info()
        self.fftwf_plan = self.fftwf_plan_dft_r2c_1d(self.size, input_ptr, output_ptr, 1)

    def dft(self, data, typecode='h'):
        if type(data) is str:
            a = array.array(typecode, data)
            for index, value in enumerate(a):
                self.real_input[index] = float(value)
        elif type(data) is array.array:
            for index, value in enumerate(data):
                self.real_input[index] = float(value)

        self.fftwf_execute(self.fftwf_plan)

        for i in range(len(self.amplitude)):
            self.amplitude[i] = math.hypot(self.complex_output[i * 2], self.complex_output[i * 2 + 1])
            # self.phase[i] = math.atan2(self.complex_output[i * 2 + 1], self.complex_output[i * 2])

        return self.amplitude  # , self.phase


if __name__ == '__main__':
    N = 128
    rate = 16000

    data = array.array('h', [1] * N)
    w = 2 * math.pi * 1000 / rate
    for t in range(N):
        data[t] = 10 + int(100 * math.sin(w * t)) + int(200 * math.sin(2 * w * t))

    fft = FFT(N)
    print fft.dft(data)
