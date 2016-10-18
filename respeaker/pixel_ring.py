import usb_hid
from spi import spi


class PixelRing:
    mono_mode = 1
    listening_mode = 2
    waiting_mode = 3
    speaking_mode = 4

    def __init__(self):
        self.hid = usb_hid.get()

    def off(self):
        self.set_color(rgb=0)

    def set_color(self, rgb=None, r=0, g=0, b=0):
        if rgb:
            self.write(0, [self.mono_mode, rgb & 0xFF, (rgb >> 8) & 0xFF, (rgb >> 16) & 0xFF])
        else:
            self.write(0, [self.mono_mode, b, g, r])

    def listen(self, direction=None):
        if direction is None:
            self.write(0, [7, 0, 0, 0])
        else:
            self.write(0, [2, 0, direction & 0xFF, (direction >> 8) & 0xFF])

    def wait(self):
        self.write(0, [self.waiting_mode, 0, 0, 0])

    def speak(self, strength, direction):
        self.write(0, [self.speaking_mode, strength, direction & 0xFF, (direction >> 8) & 0xFF])

    def set_volume(self, volume):
        self.write(0, [5, 0, 0, volume])

    @staticmethod
    def to_bytearray(data):
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

    def write(self, address, data):
        data = self.to_bytearray(data)
        length = len(data)
        if self.hid:
            packet = bytearray([address & 0xFF, (address >> 8) & 0xFF, length & 0xFF, (length >> 8) & 0xFF]) + data
            self.hid.write(packet)
            print packet
        spi.write(address=address, data=data)

    def close(self):
        if self.hid:
            self.hid.close()


pixel_ring = PixelRing()


if __name__ == '__main__':
    import time

    pixel_ring.listen()
    time.sleep(3)
    pixel_ring.wait()
    time.sleep(3)
    for level in range(2, 8):
        pixel_ring.speak(level, 0)
        time.sleep(1)
    pixel_ring.set_volume(4)
    time.sleep(3)

    color = 0x800000
    while True:
        try:
            pixel_ring.set_color(rgb=color)
            color += 0x10
            time.sleep(1)
        except KeyboardInterrupt:
            break

    pixel_ring.off()
