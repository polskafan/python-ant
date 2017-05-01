# -*- coding: utf-8 -*-
"""ANT+ Heart Rate Device Profile

"""

##############################################################################
#
# Copyright (c) 2017, Matt Hughes
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

from __future__ import print_function

from threading import Lock

from ant.core.node import Network
from ant.core.constants import NETWORK_KEY_ANT_PLUS, NETWORK_NUMBER_PUBLIC, \
    CHANNEL_TYPE_TWOWAY_RECEIVE
from ant.core.message import ChannelBroadcastDataMessage, ChannelRequestMessage, ChannelIDMessage
import ant.core.constants as constants

class _HeartRateEvent(object):

    def __init__(self, hr):
        self.hr = hr

    def process(self, msg, channel):
        if isinstance(msg, ChannelBroadcastDataMessage):
            self.hr._set_data(msg.payload)

            if not self.hr.isPaired or self.hr.detectedDevice is None:
                # law of demeter violation for now...
                req_msg = ChannelRequestMessage(messageID=constants.MESSAGE_CHANNEL_ID)
                self.hr.node.evm.writeMessage(req_msg)

        elif isinstance(msg, ChannelIDMessage):
            m = "channelID, device number: {}, device type: {}, transmission type: {}"
            print(m.format(msg.deviceNumber, msg.deviceType, msg.transmissionType))
            self.hr._set_detected_device(msg.deviceNumber, msg.transmissionType)

class HeartRate(object):
    """ANT+ Heart Rate

    """
    def __init__(self, node, device_id=0, transmission_type=0):
        """Open a channel for heart rate data

        Device pairing is performed by using a device_id and transmission_type
        of 0. Once a device has been identified for pairing, a new channel
        should be created for the identified device.
        """
        self.node = node
        self.device_id = device_id
        self.transmission_type = transmission_type

        self.lock = Lock()
        self._computed_heart_rate = None
        self._detected_device = None

        if not self.node.running:
            raise Exception('Node must be running')

        if not self.node.networks:
            raise Exception('Node must have an available network')

        public_network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
        self.node.setNetworkKey(NETWORK_NUMBER_PUBLIC, public_network)

        self.channel = self.node.getFreeChannel()
        # todo getFreeChannel() can fail
        self.channel.registerCallback(_HeartRateEvent(self))

        self.channel.assign(public_network, CHANNEL_TYPE_TWOWAY_RECEIVE)

        self.channel.setID(0x78, device_id, transmission_type)

        self.channel.frequency = 0x39
        self.channel.period = 8070
        self.channel.searchTimeout = 30

        self.channel.open()

    def _set_data(self, data):
        # ChannelMessage prepends the channel number to the message data
        # (Incorrectly IMO)
        data_size = 9
        payload_offset = 1
        computed_heart_rate_index = 7 + payload_offset

        if len(data) != data_size:
            return

        with self.lock:
            self._computed_heart_rate = data[computed_heart_rate_index]

    def _set_detected_device(self, device_num, trans_type):
        self._detected_device = (device_num, trans_type)

    @property
    def computed_heart_rate(self):
        chr = None
        with self.lock: # necessary? don't think so...
            chr = self._computed_heart_rate
        return chr

    @property
    def detectedDevice(self):
        return self._detected_device

    @property
    def isPaired(self):
        return self.device_id != 0 or self.transmission_type != 0
