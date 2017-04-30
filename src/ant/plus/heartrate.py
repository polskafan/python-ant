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

__version__ = 'develop'

from threading import Lock

from ant.core.node import Network
from ant.core.constants import NETWORK_KEY_ANT_PLUS, NETWORK_NUMBER_PUBLIC, CHANNEL_TYPE_TWOWAY_RECEIVE
from ant.core.event import EventCallback
from ant.core.message import ChannelBroadcastDataMessage

class _HeartRateEvent(EventCallback):

    def __init__(self, hr):
        self.hr = hr

    def process(self, msg, channel):
        if isinstance(msg, ChannelBroadcastDataMessage):
            self.hr._set_data(msg.payload)
            print("heart rate is {}, channel: {}".format(msg.payload[-1], msg.channelNumber))

class HeartRate:

    def __init__(self, node, device_id=0, transmission_type=0):
        """Open a channel for heart rate data

        Device pairing is performed by using a device_id and transmission_type
        of 0. Once a device has been identified for pairing, a new channel
        should be created for the identified device.
        """
        self.node = node
        self.lock = Lock()
        self._computed_heart_rate = None

        if not self.node.running:
            raise Exception('Node must be running')

        if len(self.node.networks) == 0:
            raise Exception('Node must have an available network')

        public_network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
        self.node.setNetworkKey(NETWORK_NUMBER_PUBLIC, public_network)

        self.channel = self.node.getFreeChannel()
        # todo getFreeChannel() can fail

        self.channel.frequency = 0x39
        self.channel.period = 8070
        self.channel.searchTime = 30

        self.channel.setID(device_id, 0x78, transmission_type)

        self.channel.registerCallback(_HeartRateEvent(self))
        self.channel.assign(public_network, CHANNEL_TYPE_TWOWAY_RECEIVE)

        self.channel.open()

    def get_last_computed_heart_rate(self):
        return None

    def _set_data(self, data):
        # ChannelMessage prepends the channel number to the message data
        # (Incorrectly IMO)
        DATA_SIZE = 9
        PAYLOAD_OFFSET = 1
        COMPUTED_HEART_RATE_INDEX = 7 + PAYLOAD_OFFSET

        if len(data) != DATA_SIZE:
            return

        with self.lock:
            self._computed_heart_rate = data[COMPUTED_HEART_RATE_INDEX]

    @property
    def computed_heart_rate(self):
        chr = None
        with self.lock: # necessary? don't think so...
            chr = self._computed_heart_rate
        return chr

