# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
##############################################################################
#
# Copyright (c) 2011, Martín Raúl Villalba
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
##############################################################################

from __future__ import division, absolute_import, print_function, unicode_literals

from threading import Lock

# USB1 driver uses a USB<->Serial bridge
from serial import Serial, SerialException, SerialTimeoutException

# USB2 driver uses direct USB connection. Requires PyUSB
import usb.core
import usb.util
from usb.util import (find_descriptor, claim_interface, endpoint_direction, ENDPOINT_OUT, ENDPOINT_IN)
from usb.core import USBError

from ant.core.exceptions import DriverError
from asyncio import Event


class Driver(object):
    def __init__(self, log=None, debug=False):
        self.debug = debug
        self.log = log
        self._lock = Lock()

    def open(self):
        with self._lock:
            if self._opened:
                raise DriverError("Could not open device (already open).")

            self._open()
            if self.log:
                self.log.logOpen()

    @property
    def opened(self):
        with self._lock:
            return self._opened

    def close(self):
        with self._lock:
            if not self._opened:
                raise DriverError("Could not close device (not open).")

            self._close()
            if self.log:
                self.log.logClose()

    def read(self, count):
        if count <= 0:
            raise DriverError("Could not read from device (zero request).")
        if not self.opened:
            raise DriverError("Could not read from device (not open).")

        # TODO handle USBError exception here, probably rethrow as DriverError
        # timeouts might be handled as raising a DriverTimeoutError
        data = self._read(count)

        with self._lock:
            if self.log:
                self.log.logRead(data)
            if self.debug:
                self._dump(data, 'READ')
        return data

    def write(self, msg):
        if not self.opened:
            raise DriverError("Could not write to device (not open).")

        data = msg.encode()
        ret = self._write(data)

        with self._lock:
            if self.debug:
                self._dump(data, 'WRITE')
            if self.log:
                self.log.logWrite(data[0:ret])
        return ret

    @staticmethod
    def _dump(data, title):
        if not data:
            return

        print("========== [%s] ==========" % title)

        line, length = 0, 16
        while data:
            print('%04X' % line, *('%02X' % byte for byte in data[:length]))
            data = data[length:]
            line += length

        print()

    @property
    def _opened(self):
        raise NotImplementedError()

    def _open(self):
        raise NotImplementedError()

    def _close(self):
        raise NotImplementedError()

    def _read(self, count):
        raise NotImplementedError()

    def _write(self, data):
        raise NotImplementedError()


class USB1Driver(Driver):
    def __init__(self, device, baudRate=115200, log=None, debug=False):
        super(USB1Driver, self).__init__(log=log, debug=debug)
        self.device = device
        self.baud = baudRate
        self._serial = None

    def _open(self):
        try:
            dev = Serial(self.device, self.baud)
        except SerialException as e:
            raise DriverError(str(e))

        if not dev.isOpen():
            raise DriverError("Could not open device")

        self._serial = dev
        dev.timeout = 0.01

    @property
    def _opened(self):
        return self._serial is not None

    def _close(self):
        self._serial.close()

    def _read(self, count):
        return self._serial.read(count)

    def _write(self, data):
        try:
            count = self._serial.write(data)
            self._serial.flush()
        except SerialTimeoutException as e:
            raise DriverError(str(e))

        return count


class USB2Driver(Driver):

    def __init__(self, idVendor=0x0fcf, idProduct=0x1008, bus=None, address=None, log=None, debug=False):
        super(USB2Driver, self).__init__(log=log, debug=debug)

        self.idVendor = idVendor
        self.idProduct = idProduct
        self.bus = bus
        self.address = address

        self._epOut = None
        self._epIn = None
        self._dev = None
        self._intNum = None

        self.disconnected = Event()

    def _open(self):
        # Most of this is straight from the PyUSB example documentation
        dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct,
                            custom_match=lambda d: (d.bus == self.bus or self.bus is None) and
                                                   (d.address == self.address or self.address is None))

        if dev is None:
            raise DriverError("Could not open device (not found)")

        # make sure the kernel driver is not active
        try:
            if dev.is_kernel_driver_active(0):
                try:
                    dev.detach_kernel_driver(0)
                except usb.core.USBError as e:
                    exit("could not detach kernel driver: {}".format(e))
        except NotImplementedError:
            pass  # for non unix systems

        dev.set_configuration()
        cfg = dev.get_active_configuration()

        intf = cfg[(0, 0)]

        claim_interface(dev, intf)

        ep_out = find_descriptor(intf, custom_match=lambda ep: endpoint_direction(ep.bEndpointAddress) == ENDPOINT_OUT)
        ep_in = find_descriptor(intf, custom_match=lambda ep: endpoint_direction(ep.bEndpointAddress) == ENDPOINT_IN)

        self._epOut = ep_out
        self._epIn = ep_in
        self._dev = dev
        self._intNum = intf

    def read(self, count):
        if count <= 0:
            raise DriverError("Could not read from device (zero request).")
        if not self.opened:
            raise DriverError("Could not read from device (not open).")

        try:
            data = self._read(count)
        except USBError as e:
            if e.errno in (60, 110):
                raise e
            else:
                self.disconnected.set()
                raise e

        with self._lock:
            if self.log:
                self.log.logRead(data)
            if self.debug:
                self._dump(data, 'READ')
        return data

    @property
    def _opened(self):
        return self._dev is not None

    def _close(self):
        dev = self._dev
        usb.util.release_interface(dev, self._intNum)
        usb.util.dispose_resources(dev)
        self._dev = None
        # release 'Endpoints' objects for prevent undeleted 'Device' resource
        self._epOut = self._epIn = None

    def _read(self, count):
        return self._epIn.read(count).tobytes()

    def _write(self, data):
        # TODO handle USBError here
        return self._epOut.write(data)
