# -*- coding: utf-8 -*-
"""ANT+ Bicycle Power Device Profile

"""
# pylint: disable=not-context-manager,protected-access
##############################################################################
#
# Copyright (c) 2017, David Hari
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

from threading import Lock
from struct import Struct

from .plus import _EventHandler


POWER_ONLY_PAGE = 0x10
WHEEL_TORQUE_PAGE = 0x11
CRANK_TORQUE_PAGE = 0x12
TORQUE_AND_PEDAL_PAGE = 0x13
CRANK_TORQUE_FREQ_PAGE = 0x20


class BicyclePowerCallback(object):
    """Receives bicycle power events.
    """

    def device_found(self, deviceNumber, transmissionType):
        """Called when a device is first detected.

        The callback receives the device number and transmission type.
        When instantiating the BicyclePower class, these can be supplied
        in the device_id and transmission_type keyword parameters to
        pair with the specific device.
        """
        pass

    def power_data(self):
        """Called when power data is received.

        TODO
        """
        pass


class BicyclePower(object):
    """ANT+ Bicycle Power

    """
    def __init__(self, node, network, device_id=0, transmission_type=0, callback=None):
        """Open a channel for bicycle power data

        Device pairing is performed by using a device_id and transmission_type
        of 0. Once a device has been identified for pairing, a new channel
        should be created for the identified device.
        """
        self._event_handler = _EventHandler(self, node)

        self.callback = callback

        self.lock = Lock()
        self.eventCount = None
        self.pedalDifferentiation = False  # Whether the device can tell the difference between left and right pedals
        self.pedalContribution = None
        self.accumulatedPower = None
        self.instantaneousPower = None

        self._pageStructs = {
            # These structs define the format of the data in bytes 1 to 7. Byte 0 is the page number.
            POWER_ONLY_PAGE: Struct('<BBBHH'),
            WHEEL_TORQUE_PAGE: Struct('<xxxxxxxxx')  # TODO
        }

        CHANNEL_FREQUENCY = 0x39
        CHANNEL_PERIOD = 8182
        DEVICE_TYPE = 0x0B
        SEARCH_TIMEOUT = 30
        self._event_handler.open_channel(network, CHANNEL_FREQUENCY, CHANNEL_PERIOD,
                                         transmission_type, DEVICE_TYPE,
                                         device_id, SEARCH_TIMEOUT)

    def _set_data(self, data):
        # Note: ChannelMessage prepends the channel number to the message data
        if len(data) != 9:
            return

        with self.lock:
            if data.payload[1] == 0x10:
                self.eventCount = data.payload[2]
                if data.payload[3] == 0xFF:
                    self.pedalContribution = None
                else:
                    self.pedalDifferentiation = (data.payload[3] >> 7) == 1
                    self.pedalContribution = data.payload[3] & 0x7F
                if data.payload[4] == 0xFF:
                    self.cadence = None
                else:
                    self.cadence = data.payload[4]
                self.accumulatedPower = (data.payload[6] << 8) | data.payload[5]
                self.instantaneousPower = (data.payload[8] << 8) | data.payload[7]

        if (self.callback):
            power_data = getattr(self.callback, 'power_data', None)
            if power_data:
                power_data() #TODO

    def _set_detected_device(self, device_num, trans_type):
        with self.lock:
            self._detected_device = (device_num, trans_type)

        if (self.callback):
            device_found = getattr(self.callback, 'device_found', None)
            if device_found:
                device_found(device_num, trans_type)

    @property
    def detected_device(self):
        """A tuple representing the detected device.

        This is of the form (device_number, transmission_type). This should
        be accessed when pairing to identify the monitor that is connected.
        To specifically connect to that monitor in the future, provide the
        result to the HeartRate constructor:

        HeartRate(node, network, device_number, transmission_type)
        """
        return self._detected_device

    @property
    def state(self):
        """Returns the current state of the connection. Only when this is
        STATE_RUNNING can the data from the monitor be relied upon.
        """
        return self._event_handler._state

    @property
    def channel(self):
        """Temporary until refactoring unit tests.
        """
        return self._event_handler.channel
