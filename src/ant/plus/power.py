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

from ant.core.message import *
from .plus import DeviceProfile


CALIBRATION_PAGE = 0x01
PARAMETERS_PAGE = 0x02
POWER_ONLY_PAGE = 0x10
WHEEL_TORQUE_PAGE = 0x11
CRANK_TORQUE_PAGE = 0x12
TORQUE_AND_PEDAL_PAGE = 0x13
CRANK_TORQUE_FREQ_PAGE = 0x20

CRANK_PARAMETER_SUBPAGE = 0x01


class BicyclePower(DeviceProfile):
    """ANT+ Bicycle Power"""

    channelPeriod = 8182
    deviceType = 0x0B
    name = 'Bicycle Power'

    def __init__(self, node, network, callbacks=None, maxQueryTries=10):
        """
        :param node: The ANT node to use
        :param network: The ANT network to connect on
        :param callbacks: Dictionary of string-function pairs specifying the callbacks to
                use for each event. In addition to the events supported by `DeviceProfile`,
                `BicyclePower` also has the following:
                'onPowerData'
                'onTorqueAndPedalData'
        :param maxQueryTries: When querying the device for a parameter (such as crank length),
                this specifies the number of messages to wait for a response before giving up.
        """
        super(BicyclePower, self).__init__(node, network, callbacks)

        self.maxQueryTries = maxQueryTries
        self.numQueryTries = 0
        self.eventCount = None
        self.pedalDifferentiation = False  # Whether the device can tell the difference between left and right pedals
        self.pedalPowerRatio = None
        self.cadence = None
        self.accumulatedPower = None
        self.instantaneousPower = None
        self.leftTorque = None
        self.rightTorque = None
        self.leftPedalSmoothness = None
        self.rightPedalSmoothness = None

        self.pageStructs = {
            POWER_ONLY_PAGE: Struct('<xBBBHH'),
            WHEEL_TORQUE_PAGE: Struct('<xxxxxxxxx'),  # TODO
            CRANK_TORQUE_PAGE: Struct('<xxxxxxxxx'),
            TORQUE_AND_PEDAL_PAGE: Struct('<xBBBBBxx'),
            CRANK_TORQUE_FREQ_PAGE: Struct('<xxxxxxxxx')
        }

    def open(self, channelId=None, searchTimeout=30):
        self.numQueryTries = 0
        if 'onCrankLengthSuccess' in self.callbacks:
            del self.callbacks['onCrankLengthSuccess']
        if 'onCrankLengthTimeout' in self.callbacks:
            del self.callbacks['onCrankLengthTimeout']
        super(BicyclePower, self).open(channelId, searchTimeout)

    def requestParameter(self, paramSubPage):
        """
        Queries a parameter from the device.
        """
        payload = bytes([
            0x46,               # Common Page 70: Request Data Page
            0xFF, 0xFF,         # Reserved
            paramSubPage,       # Sub-page
            0xFF,               # Invalid
            self.maxQueryTries, # Number of times to transmit requested page
            0x02,               # Page 2 (get/set parameters)
            0x01                # Command type: request data page
        ])
        request = ChannelAcknowledgedDataMessage(data=payload)
        self.channel.send(request)

    def getCrankLength(self, onSuccess, onTimeout=None):
        """
        Queries the crank length from the device. The `callback` function is called when
        the device responds with the parameter value.
        :param onSuccess: Function or lambda which called when the device responds with the value.
        :param onTimeout: Called if response does not come within `self.maxQueryTries` number of messages.
        """
        if 'onCrankLengthSuccess' not in self.callbacks:
            self.callbacks['onCrankLengthSuccess'] = onSuccess
            self.callbacks['onCrankLengthTimeout'] = onTimeout
            self.numQueryTries = 0
            self.requestParameter(CRANK_PARAMETER_SUBPAGE)

    def setCrankLength(self, value):
        """
        Sets the crank length on the device.
        """
        rawCrankValue = int((value - 110.0) / 0.5)
        payload = bytes([
            0x02,               # Data Page: Get/Set Bicycle Parameters
            0x01,               # Sub-page: Crank Parameters
            0xFF, 0xFF,         # Reserved
            rawCrankValue,
            0x00,               # Sensor Status, read-only
            0x00,               # Sensor Capabilities, read-only
            0xFF                # Reserved
        ])
        request = ChannelAcknowledgedDataMessage(data=payload)
        self.channel.send(request)

    def process(self, msg, channel):
        # If we have a callback waiting for a parameter, check if the message has come yet
        crankLengthCallback = self.callbacks.get('onCrankLengthSuccess')
        if crankLengthCallback:
            if self.numQueryTries >= self.maxQueryTries:
                # Give up if we've waited for too long, and call the timeout callback
                self.numQueryTries = 0
                del self.callbacks['onCrankLengthSuccess']
                timeoutCallback = self.callbacks.get('onCrankLengthTimeout')
                if timeoutCallback:
                    del self.callbacks['onCrankLengthTimeout']
                    timeoutCallback()
            else:
                # Check if it's the parameter response message
                if isinstance(msg, ChannelBroadcastDataMessage)\
                        and msg.data[0] == PARAMETERS_PAGE\
                        and msg.data[1] == CRANK_PARAMETER_SUBPAGE:
                    rawCrankValue = msg.data[4]
                    actualLength = None if rawCrankValue == 0xFF else (rawCrankValue * 0.5 + 110.0)
                    # Could also get sensor status and capabilities from bytes 5 and 6
                    self.numQueryTries = 0
                    del self.callbacks['onCrankLengthSuccess']
                    crankLengthCallback(actualLength)
                else:
                    super(BicyclePower, self).process(msg, channel)
            self.numQueryTries += 1
        else:
            super(BicyclePower, self).process(msg, channel)

    def processData(self, data):
        page = data[0]
        with self.lock:
            if page == POWER_ONLY_PAGE:
                self.eventCount, pedalPowerByte, self.cadence,\
                self.accumulatedPower, self.instantaneousPower\
                    = self.pageStructs[POWER_ONLY_PAGE].unpack(data)

                if pedalPowerByte == 0xFF:  # Pedal power not used
                    self.pedalPowerRatio = None
                else:
                    self.pedalDifferentiation = (pedalPowerByte >> 7) == 1
                    self.pedalPowerRatio = (pedalPowerByte & 0x7F) / 100  # Convert from percent to fraction

                if self.cadence == 0xFF:  # Invalid value
                    self.cadence = None

                callback = self.callbacks.get('onPowerData')
                if callback:
                    callback(self.eventCount, self.pedalDifferentiation, self.pedalPowerRatio,
                             self.cadence, self.accumulatedPower, self.instantaneousPower)

            elif page == TORQUE_AND_PEDAL_PAGE:
                self.eventCount, self.leftTorque, self.rightTorque,\
                self.leftPedalSmoothness, self.rightPedalSmoothness\
                    = self.pageStructs[TORQUE_AND_PEDAL_PAGE].unpack(data)

                self.leftTorque = convertPercent(self.leftTorque)
                self.rightTorque = convertPercent(self.rightTorque)
                self.leftPedalSmoothness = convertPercent(self.leftPedalSmoothness)
                if self.rightPedalSmoothness == 0xFE:
                    self.rightPedalSmoothness = None  # self.leftPedalSmoothness contains combined pedal smoothness
                else:
                    self.rightPedalSmoothness = convertPercent(self.rightPedalSmoothness)

                callback = self.callbacks.get('onTorqueAndPedalData')
                if callback:
                    callback(self.eventCount, self.leftTorque, self.rightTorque,
                             self.leftPedalSmoothness, self.rightPedalSmoothness)


# Used by Torque Effectiveness and Pedal Smoothness page. Assumes value is in 1/2% increments.
def convertPercent(value):
    return None if value == 0xFF else (value / 200)