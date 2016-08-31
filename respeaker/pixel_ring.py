from hid import INTERFACE, usb_backend
from spi import SPI


class PixelRing:
    def __init__(self):
        self.device = self.get_hid()
        if not self.device:
            self.device = SPI()

    @staticmethod
    def get_hid():
        interface = INTERFACE[usb_backend]
        boards = interface.getAllConnectedInterface()
        if boards:
            return boards[0]

    def off(self):
        self.set_color(rgb=0)

    def set_color(self, r=0, g=0, b=0, rgb=None):
        if rgb:
            self.write(0, [1, rgb & 0xFF, (rgb >> 8) & 0xFF, (rgb >> 16) & 0xFF])
        else:
            self.write(0, [1, b, g, r])

    def listen(self, direction):
        self.write(0, [2, 0, direction & 0xFF, (direction >> 8) & 0xFF])

    def wait(self):
        self.write(0, [3, 0, 0, 0])

    def speak(self, strength, direction):
        self.write(0, [4, strength, direction & 0xFF, (direction >> 8) & 0xFF])

    def set_volume(self, volume):
        self.write(0, [5, 0, 0, volume])

    def to_bytearray(self, data):
        if type(data) is int:
            array = bytearray([data & 0xFF])
        elif type(data) is bytearray:
            array = data
        elif type(data) is str:
            array = bytearray(data)
        elif type(data) is list:
            array = bytearray(data)
        else:
            raise TypeError('%s is not supported' % type(data))

        return array

    def _write(self, data):
        self.device.write(data)

    def write(self, address, data):
        data = self.to_bytearray(data)
        length = len(data)
        packet = bytearray([address & 0xFF, (address >> 8) & 0xFF, length & 0xFF, (length >> 8) & 0xFF]) + data
        self._write(packet)

    def close(self):
        self.device.close()


if __name__ == '__main__':
    import time

    ring = PixelRing()
    ring.listen(0)
    time.sleep(3)
    ring.wait()
    time.sleep(3)
    for level in range(2, 8):
        ring.speak(level, 0)
        time.sleep(1)
    ring.set_volume(4)
    time.sleep(3)

    color = 0x800000
    while True:
        try:
            ring.set_color(rgb=color)
            color += 0x10
            time.sleep(1)
        except KeyboardInterrupt:
            break

    ring.off()
