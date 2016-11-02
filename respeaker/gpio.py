"""
Linux SysFS-based native GPIO implementation Based on https://github.com/derekstavis/python-sysfs-gpio

The MIT License (MIT)

Copyright (c) 2016 Yihui Xiong
Copyright (c) 2014 Derek Willian Stavis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import logging
import os
import select
from threading import Thread

Logger = logging.getLogger(__file__)

# Sysfs constants

SYSFS_BASE_PATH = '/sys/class/gpio'

SYSFS_EXPORT_PATH = SYSFS_BASE_PATH + '/export'
SYSFS_UNEXPORT_PATH = SYSFS_BASE_PATH + '/unexport'

SYSFS_GPIO_PATH = SYSFS_BASE_PATH + '/gpio%d'
SYSFS_GPIO_DIRECTION_PATH = SYSFS_GPIO_PATH + '/direction'
SYSFS_GPIO_EDGE_PATH = SYSFS_GPIO_PATH + '/edge'
SYSFS_GPIO_VALUE_PATH = SYSFS_GPIO_PATH + '/value'
SYSFS_GPIO_ACTIVE_LOW_PATH = SYSFS_GPIO_PATH + '/active_low'

SYSFS_GPIO_VALUE_LOW = '0'
SYSFS_GPIO_VALUE_HIGH = '1'

EPOLL_TIMEOUT = 1  # second

# Public interface

INPUT = 'in'
OUTPUT = 'out'

# Compatible with MRAA
DIR_IN = INPUT
DIR_OUT = OUTPUT

RISING = 'rising'
FALLING = 'falling'
BOTH = 'both'

ACTIVE_LOW_ON = 1
ACTIVE_LOW_OFF = 0

DIRECTIONS = (INPUT, OUTPUT)
EDGES = (RISING, FALLING, BOTH)
ACTIVE_LOW_MODES = (ACTIVE_LOW_ON, ACTIVE_LOW_OFF)


class Gpio(object):
    """
    Represent a pin in SysFS
    """

    def __init__(self, number, direction=INPUT, callback=None, edge=None, active_low=0):
        """
        @type  number: int
        @param number: The pin number
        @type  direction: int
        @param direction: Pin direction, enumerated by C{Direction}
        @type  callback: callable
        @param callback: Method be called when pin changes state
        @type  edge: int
        @param edge: The edge transition that triggers callback,
                     enumerated by C{Edge}
        @type active_low: int
        @param active_low: Indicator of whether this pin uses inverted
                           logic for HIGH-LOW transitions.
        """
        self._number = number
        self._direction = direction
        self._callback = callback
        self._active_low = active_low

        if not os.path.isdir(self._sysfs_gpio_value_path()):
            with open(SYSFS_EXPORT_PATH, 'w') as export:
                export.write('%d' % number)
        else:
            Logger.debug("SysfsGPIO: Pin %d already exported" % number)

        self._fd = open(self._sysfs_gpio_value_path(), 'r+')

        if callback and not edge:
            raise Exception('You must supply a edge to trigger callback on')

        with open(self._sysfs_gpio_direction_path(), 'w') as fsdir:
            fsdir.write(direction)

        if edge:
            with open(self._sysfs_gpio_edge_path(), 'w') as fsedge:
                fsedge.write(edge)
                self._poll = select.epoll()
                self._poll.register(self, (select.EPOLLPRI | select.EPOLLET))
                self.thread = Thread(target=self._run)
                self.thread.daemon = True
                self._running = True
                self.start()

        if active_low:
            if active_low not in ACTIVE_LOW_MODES:
                raise Exception('You must supply a value for active_low which is either 0 or 1.')
            with open(self._sysfs_gpio_active_low_path(), 'w') as fsactive_low:
                fsactive_low.write(str(active_low))

    @property
    def callback(self):
        """
        Gets this pin callback
        """
        return self._callback

    @callback.setter
    def callback(self, value):
        """
        Sets this pin callback
        """
        self._callback = value

    @property
    def direction(self):
        """
        Pin direction
        """
        return self._direction

    @property
    def number(self):
        """
        Pin number
        """
        return self._number

    @property
    def active_low(self):
        """
        Pin number
        """
        return self._active_low

    def dir(self, direction):
        self._direction = direction
        with open(self._sysfs_gpio_direction_path(), 'w') as fsdir:
            fsdir.write(direction)

    def set(self):
        """
        Set pin to HIGH logic setLevel
        """
        self._fd.write(SYSFS_GPIO_VALUE_HIGH)
        self._fd.seek(0)

    def reset(self):
        """
        Set pin to LOW logic setLevel
        """
        self._fd.write(SYSFS_GPIO_VALUE_LOW)
        self._fd.seek(0)

    def read(self):
        """
        Read pin value

        @rtype: int
        @return: I{0} when LOW, I{1} when HIGH
        """
        val = self._fd.read()
        self._fd.seek(0)
        return int(val)

    def write(self, value):
        if value:
            self.set()
        else:
            self.reset()

    def close(self):
        self._running = False
        self._fd.close()

    def fileno(self):
        """
        Get the file descriptor associated with this pin.

        @rtype: int
        @return: File descriptor
        """
        return self._fd.fileno()

    def changed(self, state):
        if callable(self._callback):
            self._callback(self.number, state)

    def _run(self):

        while self._running:
            events = self._poll.poll(EPOLL_TIMEOUT)
            for fd, event in events:
                if not (event & (select.EPOLLPRI | select.EPOLLET)):
                    continue

                self.changed(self.read())

    def _sysfs_gpio_value_path(self):
        """
        Get the file that represent the value of this pin.

        @rtype: str
        @return: the path to sysfs value file
        """
        return SYSFS_GPIO_VALUE_PATH % self.number

    def _sysfs_gpio_direction_path(self):
        """
        Get the file that represent the direction of this pin.

        @rtype: str
        @return: the path to sysfs direction file
        """
        return SYSFS_GPIO_DIRECTION_PATH % self.number

    def _sysfs_gpio_edge_path(self):
        """
        Get the file that represent the edge that will trigger an interrupt.

        @rtype: str
        @return: the path to sysfs edge file
        """
        return SYSFS_GPIO_EDGE_PATH % self.number

    def _sysfs_gpio_active_low_path(self):
        """
        Get the file that represents the active_low setting for this pin.

        @rtype: str
        @return: the path to sysfs active_low file
        """
        return SYSFS_GPIO_ACTIVE_LOW_PATH % self.number


__all__ = ('DIRECTIONS', 'INPUT', 'OUTPUT', 'DIR_IN', 'DIR_OUT', 'EDGES', 'RISING', 'FALLING', 'BOTH', 'Gpio')
