# -*- coding: utf-8 -*-
"""ANT+ Device Profile connection and event handling

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
from threading import Lock

from ant.core.constants import CHANNEL_TYPE_TWOWAY_RECEIVE
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
        self.channel.searchTimeout = search_timeout / 2.5  # ANT spec says each count is equivalent to 2.5 seconds.

        self.channel.open()

        self._state = STATE_SEARCHING

    def close_channel(self):
        # TODO this can raise ChannelError if it can't close.
        # TODO it can also block indefinitely if it doesn't receive a ChannelEventResponseMessage with the right channel number and message code.
        self.channel.close()

    def process(self, msg, channel):
        """Handles incoming channel messages

        Converts messages to ANT+ Heart Rate specific data.
        """
        if isinstance(msg, ChannelBroadcastDataMessage):
            self.device_profile._set_data(msg.payload)

            if self.device_profile.detected_device is None:
                req_msg = ChannelRequestMessage(messageID=constants.MESSAGE_CHANNEL_ID)
                self.node.send(req_msg)

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


class DeviceProfile(object):

    channelFrequency = 0x39  # Subclasses can override if this needs to be different
    channelPeriod = 0   # Subclasses should override
    deviceType = 0      # Subclasses should override
    name = 'Ant Device'

    def __init__(self, node, network, callback=None):
        # onDeviceDetected
        # onSearchTimeout
        # onData
        self.node = node
        self.network = network
        self.callback = callback
        self.channel = None
        self.lock = Lock()

    def pair(self, channelId=None, searchTimeout=30):
        """Pairs with a device and opens a channel for communicating.

        :param channelId: The unique ID for each device link in a network.
                Set to None to find any device of this type. Set to an instance of
                `ant.node.ChannelID` to pair with a specific device.
        :param searchTimeout: Time to allow for searching, in seconds. If a device is
                not found within this time, an error will be raised.
        """
        deviceNumber = 0 if channelId is None else channelId.number
        deviceType = self.deviceType if channelId is None else channelId.type
        transmissionType = 0 if channelId is None else channelId.transmissionType

        self.channel = self.node.getFreeChannel()
        self.channel.registerCallback(self)
        self.channel.assign(self.network, CHANNEL_TYPE_TWOWAY_RECEIVE)
        self.channel.setID(deviceType, deviceNumber, transmissionType)
        self.channel.frequency = self.channelFrequency
        self.channel.period = self.channelPeriod
        self.channel.searchTimeout = searchTimeout // 2.5  # ANT spec says each count is equivalent to 2.5 seconds.

        self.channel.open()

    def close(self):
        self.channel.close()

    def wrapDifference(self, current, previous, max):
        if previous > current:
            correction = current + max
            difference = correction - previous
        else:
            difference = current - previous
        return difference

    def _set_data(self, data):
        pass

    def process(self, msg, channel):
        """Handles incoming channel messages

        Converts messages to ANT+ device specific data.
        """
        if isinstance(msg, ChannelBroadcastDataMessage):
            self._set_data(msg.payload)

            if self.detected_device is None:
                req_msg = ChannelRequestMessage(messageID=constants.MESSAGE_CHANNEL_ID)
                self.node.send(req_msg)

        elif isinstance(msg, ChannelIDMessage):
            self._set_detected_device(msg.deviceNumber, msg.transmissionType)
            self._state = STATE_RUNNING

        elif isinstance(msg, ChannelEventResponseMessage):
            if msg.messageCode == constants.EVENT_CHANNEL_CLOSED:
                self._state = STATE_CLOSED
            elif msg.messageCode == constants.EVENT_RX_SEARCH_TIMEOUT:
                self._state = STATE_SEARCH_TIMEOUT
            elif msg.messageCode == constants.EVENT_RX_FAIL_GO_TO_SEARCH:
                self._state = STATE_SEARCHING
