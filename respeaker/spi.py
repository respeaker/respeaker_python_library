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

import platform

if platform.machine() == 'mips':
    import mraa
    import time


    class SPI:
        def __init__(self, sck=15, mosi=17, miso=16, cs=14):
            self.sck = mraa.Gpio(sck)
            self.mosi = mraa.Gpio(mosi)
            self.miso = mraa.Gpio(miso)
            self.cs = mraa.Gpio(cs)

            self.sck.dir(mraa.DIR_OUT)
            self.mosi.dir(mraa.DIR_OUT)
            self.miso.dir(mraa.DIR_IN)
            self.cs.dir(mraa.DIR_OUT)

            self.cs.write(1)

            self.frequency(10000000)
            self.format(8, 0)

        def frequency(self, hz=10000000):
            self.freq = hz

        def format(self, bits=8, mode=0):
            self.bits = bits
            self.mode = mode
            self.polarity = (mode >> 1) & 1
            self.phase = mode & 1
            self.sck.write(self.polarity)

        def write_byte(self, data):
            read = 0
            for bit in range(self.bits - 1, -1, -1):
                self.mosi.write((data >> bit) & 0x01)

                if 0 == self.phase:
                    read |= self.miso.read() << bit

                self.sck.write(1 - self.polarity)
                # time.sleep(0.5 / self.freq)

                if 1 == self.phase:
                    read |= self.miso.read() << bit

                self.sck.write(self.polarity)
                # time.sleep(0.5 / self.freq)

            return read

        def write(self, data):
            response = bytearray()
            self.cs.write(0)
            if type(data) is int:
                response.append(self.write_byte(data))
            elif type(data) is bytearray:
                for b in data:
                    response.append(self.write_byte(b))
            elif type(data) is str:
                for b in bytearray(data):
                    response.append(self.write_byte(b))
            elif type(data) is list:
                for item in data:
                    self.write(item)
            else:
                self.cs.write(1)
                raise TypeError('%s is not supported' % type(data))

            self.cs.write(1)
            return response

        def close(self):
            pass
else:
    class SPI:
        def __init__(self):
            pass

        def write(self, data):
            pass

        def close(self):
            pass

if __name__ == '__main__':
    dev = SPI()
    while True:
        dev.write('hello\n')
        time.sleep(1)
