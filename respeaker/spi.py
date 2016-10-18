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


CRC8_TABLE = (
    0x00, 0x07, 0x0e, 0x09, 0x1c, 0x1b, 0x12, 0x15,
    0x38, 0x3f, 0x36, 0x31, 0x24, 0x23, 0x2a, 0x2d,
    0x70, 0x77, 0x7e, 0x79, 0x6c, 0x6b, 0x62, 0x65,
    0x48, 0x4f, 0x46, 0x41, 0x54, 0x53, 0x5a, 0x5d,
    0xe0, 0xe7, 0xee, 0xe9, 0xfc, 0xfb, 0xf2, 0xf5,
    0xd8, 0xdf, 0xd6, 0xd1, 0xc4, 0xc3, 0xca, 0xcd,
    0x90, 0x97, 0x9e, 0x99, 0x8c, 0x8b, 0x82, 0x85,
    0xa8, 0xaf, 0xa6, 0xa1, 0xb4, 0xb3, 0xba, 0xbd,
    0xc7, 0xc0, 0xc9, 0xce, 0xdb, 0xdc, 0xd5, 0xd2,
    0xff, 0xf8, 0xf1, 0xf6, 0xe3, 0xe4, 0xed, 0xea,
    0xb7, 0xb0, 0xb9, 0xbe, 0xab, 0xac, 0xa5, 0xa2,
    0x8f, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9d, 0x9a,
    0x27, 0x20, 0x29, 0x2e, 0x3b, 0x3c, 0x35, 0x32,
    0x1f, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0d, 0x0a,
    0x57, 0x50, 0x59, 0x5e, 0x4b, 0x4c, 0x45, 0x42,
    0x6f, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7d, 0x7a,
    0x89, 0x8e, 0x87, 0x80, 0x95, 0x92, 0x9b, 0x9c,
    0xb1, 0xb6, 0xbf, 0xb8, 0xad, 0xaa, 0xa3, 0xa4,
    0xf9, 0xfe, 0xf7, 0xf0, 0xe5, 0xe2, 0xeb, 0xec,
    0xc1, 0xc6, 0xcf, 0xc8, 0xdd, 0xda, 0xd3, 0xd4,
    0x69, 0x6e, 0x67, 0x60, 0x75, 0x72, 0x7b, 0x7c,
    0x51, 0x56, 0x5f, 0x58, 0x4d, 0x4a, 0x43, 0x44,
    0x19, 0x1e, 0x17, 0x10, 0x05, 0x02, 0x0b, 0x0c,
    0x21, 0x26, 0x2f, 0x28, 0x3d, 0x3a, 0x33, 0x34,
    0x4e, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5c, 0x5b,
    0x76, 0x71, 0x78, 0x7f, 0x6a, 0x6d, 0x64, 0x63,
    0x3e, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2c, 0x2b,
    0x06, 0x01, 0x08, 0x0f, 0x1a, 0x1d, 0x14, 0x13,
    0xae, 0xa9, 0xa0, 0xa7, 0xb2, 0xb5, 0xbc, 0xbb,
    0x96, 0x91, 0x98, 0x9f, 0x8a, 0x8d, 0x84, 0x83,
    0xde, 0xd9, 0xd0, 0xd7, 0xc2, 0xc5, 0xcc, 0xcb,
    0xe6, 0xe1, 0xe8, 0xef, 0xfa, 0xfd, 0xf4, 0xf3
)


def crc8(data):
    result = 0
    for b in data:
        result = CRC8_TABLE[result ^ b]
    return result


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

        def _write(self, data):
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

        def write(self, data=None, address=None):
            if address:
                self.write_byte(0xA5)           # prefix
                self.write_byte(address)        # address
                self.write_byte(len(data))      # length
                response = self._write(data)    # data
                self.write_byte(crc8(data))     # crc8
            else:
                response = self._write(data)

            return response

        def close(self):
            pass
else:
    class SPI:
        def __init__(self):
            pass

        def write(self, data=None, address=None):
            pass

        def close(self):
            pass


spi = SPI()


if __name__ == '__main__':
    while True:
        spi.write('hello\n')
        time.sleep(1)
