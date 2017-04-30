# -*- coding: utf-8 -*-

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

import unittest

from ant.core import event, message
from ant.core.constants import NETWORK_KEY_ANT_PLUS, CHANNEL_TYPE_TWOWAY_RECEIVE
from ant.core.node import Network, Node, Channel, Device
from ant.core.message import ChannelBroadcastDataMessage, ChannelIDMessage, ChannelFrequencyMessage, ChannelAssignMessage, ChannelPeriodMessage, ChannelSearchTimeoutMessage, ChannelOpenMessage

from ant.plus.heartrate import HeartRate

class FakeEventMachine():
    def __init__(self):
        self.messages = []

    def writeMessage(self, msg):
        self.messages.append(msg)
        return self

    def waitForAck(self, msg):
        return None

    def registerCallback(self, callback):
        pass

class FakeChannel(Channel):
    def __init__(self, node, number=0):
        super(FakeChannel, self).__init__(node, number)

    def assign(self, network, channelType):
        self.assigned_network = network
        self.assigned_channel_type = channelType
        self.assigned_channel_number = self.number
        super(FakeChannel, self).assign(network, channelType)

    def open(self):
        self.open_called = True
        super(FakeChannel, self).open()


class FakeNode(Node):
    def __init__(self, event_machine):
        super(FakeNode, self).__init__(None, None)

        # Properties of the real thing
        self.evm = event_machine
        self.networks = [None] * 3
        self.channels = [FakeChannel(self, i) for i in range(0, 8)]

        # Sensing
        self.network_number = None
        self.network_key = None
        self._running = True
        self.num_channels = 8

    def set_running(self, running):
        self._running = running

    running = property(lambda self: self._running,
                       set_running)

    def reset(self):
        pass

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def setNetworkKey(self, number, network=None):
        self.network_number = number
        self.network_key = network.key

    def use_all_channels(self):
        for channel in self.channels:
            channel.network = 1

class HeartRateTest(unittest.TestCase):
    def setUp(self):
        self.event_machine = FakeEventMachine()
        self.node = FakeNode(self.event_machine)

    def test_heartrate_requires_running_node(self):
        self.node.running = False

        with self.assertRaises(Exception):
            hr = HeartRate(self.node)

    def test_heartrate_requires_available_network(self):
        self.node.networks = []

        with self.assertRaises(Exception):
            hr = HeartRate(self.node)

    def test_heartrate_node_setup(self):
        hr = HeartRate(self.node)

        self.assertEqual(0, self.node.network_number)
        self.assertEqual(NETWORK_KEY_ANT_PLUS,
                         self.node.network_key)

    def test_heartrate_requires_free_channel(self):
        self.node.use_all_channels()

        with self.assertRaises(Exception):
            hr = HeartRate(self.node)

    def test_heartrate_default_channel_setup(self):
        hr = HeartRate(self.node)

        self.assertEqual(0x39, hr.channel.frequency)
        self.assertEqual(8070, hr.channel.period)
        self.assertEqual(30, hr.channel.searchTimeout)

        # TODO device is the wrong name. The ANT docs refer to this
        # structure as a channel ID
        pairing_device = Device(0, 0x78, 0)
        self.assertEqual(pairing_device.number, hr.channel.device.number)
        self.assertEqual(pairing_device.type, hr.channel.device.type)
        self.assertEqual(pairing_device.transmissionType,
                         hr.channel.device.transmissionType)

        public_network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
        self.assertEqual(public_network.key, hr.channel.assigned_network.key)
        self.assertEqual(public_network.name, hr.channel.assigned_network.name)
        self.assertEqual(public_network.number, hr.channel.assigned_network.number)

        self.assertEqual(CHANNEL_TYPE_TWOWAY_RECEIVE, hr.channel.assigned_channel_type)
        self.assertEqual(0, hr.channel.assigned_channel_number)

        self.assertEqual(True, hr.channel.open_called)

    def test_heartrate_paired_channel_setup(self):
        hr = HeartRate(self.node, device_id = 1234, transmission_type = 2)

        device = Device(1234, 0x78, 2)
        self.assertEqual(device.number, hr.channel.device.number)
        self.assertEqual(device.type, hr.channel.device.type)
        self.assertEqual(device.transmissionType,
                         hr.channel.device.transmissionType)

    def test_heartrate_receives_channel_broadcast_message(self):
        hr = HeartRate(self.node)

        self.assertEqual(None, hr.get_last_computed_heart_rate())

        test_data = bytearray(b'\x00' * 8)
        test_data[7] = b'\x64'
        hr.channel.process(ChannelBroadcastDataMessage(data=test_data))

        self.assertEqual(100, hr.computed_heart_rate)

    def test_heartrate_channel_order_of_operations(self):
        # This test really belongs to the Channel class, but it doesn't
        # handle this... yet.
        hr = HeartRate(self.node)

        messages = self.event_machine.messages
        self.assertEqual(6, len(messages))

        # Assignment must come first (9.5.2.2)
        self.assertIsInstance(messages[0], ChannelAssignMessage)

        # The rest can come in any order, though setting Channel ID is
        # typically second in the documentation
        self.assertIsInstance(messages[1], ChannelIDMessage)
        self.assertIsInstance(messages[2], ChannelFrequencyMessage)
        self.assertIsInstance(messages[3], ChannelPeriodMessage)
        self.assertIsInstance(messages[4], ChannelSearchTimeoutMessage)

        # Open must be last (9.5.4.2)
        self.assertIsInstance(messages[5], ChannelOpenMessage)

