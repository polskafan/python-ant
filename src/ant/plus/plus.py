# -*- coding: utf-8 -*-
"""ANT+ Device Profile State Machine and Low Level Event Handling

"""
# pylint: disable=not-context-manager,protected-access
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

from ant.core.node import Network
from ant.core.constants import NETWORK_KEY_ANT_PLUS, NETWORK_NUMBER_PUBLIC, \
    CHANNEL_TYPE_TWOWAY_RECEIVE
from ant.core.message import ChannelBroadcastDataMessage, ChannelRequestMessage, ChannelIDMessage, \
    ChannelEventResponseMessage
import ant.core.constants as constants

# State Machine Parameters
# TODO replace with PEP 435 enum
# TODO move most of this to Node or Channel
STATE_SEARCHING = 1
STATE_SEARCH_TIMEOUT = 2
STATE_CLOSED = 3
STATE_RUNNING = 4


class _EventHandler(object):

    def __init__(self, device_profile, node):
        self.device_profile = device_profile
        self.node = node
        self.channel = None
        self._state = None

        if not self.node.running:
            raise Exception('Node must be running')

        # Not sure about this check, because the public network is always 0.
        if not self.node.networks:
            raise Exception('Node must have an available network')

    def open_channel(self, network, frequency, period, transmission_type, device_type,
                     device_number, search_timeout):
        self.channel = self.node.getFreeChannel()
        # todo getFreeChannel() can fail
        self.channel.registerCallback(self)
        self.channel.assign(network, CHANNEL_TYPE_TWOWAY_RECEIVE)
        self.channel.setID(device_type, device_number, transmission_type)
        self.channel.frequency = frequency
        self.channel.period = period
        self.channel.searchTimeout = search_timeout # note, this is not in seconds

        self.channel.open()

        self._state = STATE_SEARCHING

    def process(self, msg, channel):
        """Handles incoming channel messages

        Converts messages to ANT+ Heart Rate specific data.
        """
        if isinstance(msg, ChannelBroadcastDataMessage):
            self.device_profile._set_data(msg.payload)

            if self.device_profile.detected_device is None:
                req_msg = ChannelRequestMessage(messageID=constants.MESSAGE_CHANNEL_ID)
                # law of demeter violation for now... node or channel should provide
                # for writing messages
                self.node.evm.writeMessage(req_msg)

        elif isinstance(msg, ChannelIDMessage):
            self.device_profile._set_detected_device(msg.deviceNumber, msg.transmissionType)
            self._state = STATE_RUNNING

        elif isinstance(msg, ChannelEventResponseMessage):
            if msg.messageCode == constants.EVENT_CHANNEL_CLOSED:
                self._state = STATE_CLOSED
            elif msg.messageCode == constants.EVENT_RX_SEARCH_TIMEOUT:
                self._state = STATE_SEARCH_TIMEOUT
            elif msg.messageCode == constants.EVENT_RX_FAIL_GO_TO_SEARCH:
                self._state = STATE_SEARCHING