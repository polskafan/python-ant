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

from struct import Struct

from .plus import DeviceProfile


POWER_ONLY_PAGE = 0x10
WHEEL_TORQUE_PAGE = 0x11
CRANK_TORQUE_PAGE = 0x12
TORQUE_AND_PEDAL_PAGE = 0x13
CRANK_TORQUE_FREQ_PAGE = 0x20


class BicyclePower(DeviceProfile):
    """ANT+ Bicycle Power"""

    channelPeriod = 8182
    deviceType = 0x0B

    def __init__(self, node, network, callbacks=None):
        """
        :param node: The ANT node to use
        :param network: The ANT network to connect on
        :param callbacks: Dictionary of string-function pairs specifying the callbacks to
                use for each event. In addition to the events supported by `DeviceProfile`,
                `BicyclePower` also has the following:
                'onPowerData'
        """
        super(DeviceProfile, self).__init__(node, network, callbacks)

        self.eventCount = None
        self.pedalDifferentiation = False  # Whether the device can tell the difference between left and right pedals
        self.pedalContribution = None
        self.cadence = None
        self.accumulatedPower = None
        self.instantaneousPower = None

        self.pageStructs = {
            # These structs define the format of the data in bytes 1 to 7. Byte 0 is the page number.
            POWER_ONLY_PAGE: Struct('<xBBBHH'),
            WHEEL_TORQUE_PAGE: Struct('<xxxxxxxxx')  # TODO
        }

    def processData(self, data):
        with self.lock:
            if data.payload[0] == POWER_ONLY_PAGE:
                self.eventCount, pedalPowerByte, self.cadence,\
                self.accumulatedPower, self.instantaneousPower = self.pageStructs[POWER_ONLY_PAGE].unpack(data)

                if pedalPowerByte == 0xFF:  # Pedal power not used
                    self.pedalContribution = None
                else:
                    self.pedalDifferentiation = (pedalPowerByte >> 7) == 1
                    self.pedalContribution = pedalPowerByte & 0x7F

                if self.cadence == 0xFF:  # Invalid value
                    self.cadence = None

        onPowerData = self.callbacks.get('onPowerData')
        if onPowerData:
            onPowerData(self.eventCount, self.pedalDifferentiation, self.pedalContribution,
                        self.cadence, self.accumulatedPower, self.instantaneousPower)
