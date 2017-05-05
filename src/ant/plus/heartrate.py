# -*- coding: utf-8 -*-
"""ANT+ Heart Rate Device Profile

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

class HeartRateCallback(object):
    """Receives heart rate events.
    """

    def device_found(self, device_number, transmission_type):
        """Called when a device is first detected.

        The callback receives the device number and transmission type.
        When instantiating the HeartRate class, these can be supplied
        in the device_id and transmission_type keyword parameters to
        pair with the specific device.
        """
        pass

    def heartrate_data(self, computed_heartrate): # rest to come soon
        """Called when heart rate data is received.

        Currently only computed heart rate is returned.
        TODO: R-R interval data.
        """
        pass


class _EventHandler(object):

    def __init__(self, heartrate):
        self.heartrate = heartrate

    def process(self, msg, channel):
        """Handles incoming channel messages

        Converts messages to ANT+ Heart Rate specific data.
        """
        if isinstance(msg, ChannelBroadcastDataMessage):
            self.heartrate._set_data(msg.payload)

            if (self.heartrate.callback):
                heartrate_data = getattr(self.heartrate.callback, 'heartrate_data', None)
                if heartrate_data:
                    heartrate_data(self.heartrate.computed_heart_rate)


            if self.heartrate.detected_device is None:
                # law of demeter violation for now...
                req_msg = ChannelRequestMessage(messageID=constants.MESSAGE_CHANNEL_ID)
                self.heartrate.node.evm.writeMessage(req_msg)

        elif isinstance(msg, ChannelIDMessage):
            self.heartrate._set_detected_device(msg.deviceNumber, msg.transmissionType)
            self.heartrate._set_state(STATE_RUNNING)

            if (self.heartrate.callback):
                device_found = getattr(self.heartrate.callback, 'device_found', None)
                if device_found:
                    device_found(msg.deviceNumber, msg.transmissionType)

        elif isinstance(msg, ChannelEventResponseMessage):
            if msg.messageCode == constants.EVENT_CHANNEL_CLOSED:
                self.heartrate._set_state(STATE_CLOSED)
            elif msg.messageCode == constants.EVENT_RX_SEARCH_TIMEOUT:
                self.heartrate._set_state(STATE_SEARCH_TIMEOUT)
            elif msg.messageCode == constants.EVENT_RX_FAIL_GO_TO_SEARCH:
                self.heartrate._set_state(STATE_SEARCHING)

class HeartRate(object):
    """ANT+ Heart Rate

    """
    def __init__(self, node, device_id=0, transmission_type=0, callback=None):
        """Open a channel for heart rate data

        Device pairing is performed by using a device_id and transmission_type
        of 0. Once a device has been identified for pairing, a new channel
        should be created for the identified device.
        """
        self.node = node
        self.device_id = device_id
        self.transmission_type = transmission_type
        self.callback = callback

        self.lock = Lock()
        self._computed_heart_rate = None
        self._detected_device = None
        self._state = None

        if not self.node.running:
            raise Exception('Node must be running')

        if not self.node.networks:
            raise Exception('Node must have an available network')

        public_network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
        self.node.setNetworkKey(NETWORK_NUMBER_PUBLIC, public_network)

        self.channel = self.node.getFreeChannel()
        # todo getFreeChannel() can fail
        self.channel.registerCallback(_EventHandler(self))

        self.channel.assign(public_network, CHANNEL_TYPE_TWOWAY_RECEIVE)

        self.channel.setID(0x78, device_id, transmission_type)

        self.channel.frequency = 0x39
        self.channel.period = 8070
        self.channel.searchTimeout = 30 # note, this is not in seconds

        self.channel.open()

        self._state = STATE_SEARCHING

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
        with self.lock:
            self._detected_device = (device_num, trans_type)

    def _set_state(self, state):
        with self.lock:
            self._state = state

    @property
    def computed_heart_rate(self):
        """The computed heart rate calculated by the connected monitor.
        """
        rate = None
        with self.lock:
            rate = self._computed_heart_rate
        return rate

    @property
    def detected_device(self):
        """A tuple representing the detected device.

        This is of the form (device_number, transmission_type). This should
        be accessed when pairing to identify the monitor that is connected.
        To specifically connect to that monitor in the future, provide the
        result to the HeartRate constructor:

        HeartRate(node, device_number, transmission_type)
        """
        return self._detected_device

    @property
    def state(self):
        """Returns the current state of the connection. Only when this is
        STATE_RUNNING can the data from the monitor be relied upon.
        """
        return self._state
