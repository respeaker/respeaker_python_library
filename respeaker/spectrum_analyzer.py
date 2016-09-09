import ctypes
import struct
import array
import math


class SpectrumAnalyzer:
    def __init__(self, n):
        self.n = 1 << math.frexp(n)[1]
        self.real_input = array.array('f', [0.0] * n)
        self.complex_output = array.array('f', [0.0] * (n * 2))
        self.amplitude = array.array('f', [0.0] * n)
        self.phase = array.array('f', [0.0] * n)

        self.fftw3f = ctypes.CDLL('libfftw3f.so')

        # fftw_plan fftw_plan_dft_r2c_1d(int n, double *in, fftw_complex *out, unsigned flags);
        self.fftwf_plan_dft_r2c_1d = self.fftw3f.fftwf_plan_dft_r2c_1d
        self.fftwf_plan_dft_r2c_1d.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint)
        self.fftwf_plan_dft_r2c_1d.restype = ctypes.c_void_p

        # void fftwf_execute(const fftwf_plan plan)
        self.fftwf_execute = self.fftw3f.fftwf_execute
        self.fftwf_execute.argtypes = (ctypes.c_void_p,)
        self.fftwf_execute.restype = None

        input_ptr, _ = self.real_input.buffer_info()
        output_ptr, _ = self.complex_output.buffer_info()
        self.fftwf_plan = self.fftwf_plan_dft_r2c_1d(n, input_ptr, output_ptr, 1)

    def analyze(self, audio_string):
        # int16_array = struct.unpack('<%dh' % (len(audio_string)/2), audio_string)  # string to 16 bit signed integer
        int16_array = array.array('h')
        int16_array.fromstring(audio_string)
        for index, int16 in enumerate(int16_array):
            self.real_input[index] = float(int16)

        print self.real_input
        self.fftwf_execute(self.fftwf_plan)
        print self.complex_output

        for i in range(self.n / 2):
            self.amplitude[i] = math.hypot(self.complex_output[2*i], self.complex_output[2*i + 1])
            self.phase[i] = math.atan2(self.complex_output[2*i] + 1, self.complex_output[2*i])

        return self.amplitude, self.phase


if __name__ == '__main__':
    N = 4
    analyzer = SpectrumAnalyzer(N)

    audio = array.array('h', [1] * N)
    audio[0] = 0
    audio[2] = 2
    audio[3] = 3
    analyzer.analyze(audio.tostring())
