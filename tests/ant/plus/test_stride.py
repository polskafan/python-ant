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
from fakes import *

from ant.plus.stride import *

from ant.core.node import Network, Node, Channel, Device
from ant.core.constants import NETWORK_KEY_ANT_PLUS, CHANNEL_TYPE_TWOWAY_RECEIVE
from ant.core.message import ChannelBroadcastDataMessage

class StrideTest(unittest.TestCase):
    def setUp(self):
        self.event_machine = FakeEventMachine()
        self.node = FakeNode(self.event_machine)
        self.network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')

    def test_default_channel_setup(self):
        stride = Stride(self.node, self.network)

        channel = stride._event_handler.channel

        self.assertEqual(0x39, channel.frequency)
        self.assertEqual(8134, channel.period)
        self.assertEqual(30, channel.searchTimeout)

        # TODO device is the wrong name. The ANT docs refer to this
        # structure as a channel ID
        pairing_device = Device(0, 0x7c, 0)
        self.assertEqual(pairing_device.number, channel.device.number)
        self.assertEqual(pairing_device.type, channel.device.type)
        self.assertEqual(pairing_device.transmissionType,
                         channel.device.transmissionType)

        self.assertEqual(self.network.key, channel.assigned_network.key)
        self.assertEqual(self.network.name, channel.assigned_network.name)
        self.assertEqual(self.network.number, channel.assigned_network.number)

        self.assertEqual(CHANNEL_TYPE_TWOWAY_RECEIVE, channel.assigned_channel_type)
        self.assertEqual(0, channel.assigned_channel_number)

        self.assertEqual(True, channel.open_called)

    def test_paired_channel_setup(self):
        stride = Stride(self.node, self.network, device_id = 1234, transmission_type = 2)

        channel = stride._event_handler.channel

        device = Device(1234, 0x7c, 2)
        self.assertEqual(device.number, channel.device.number)
        self.assertEqual(device.type, channel.device.type)
        self.assertEqual(device.transmissionType,
                         channel.device.transmissionType)

    def test_receives_page_1_channel_broadcast_message(self):
        stride = Stride(self.node, self.network)

        self.assertEqual(None, stride.stride_count)

        test_data = bytearray(b'\x00' * 8)
        test_data[0] = b'\x01'
        test_data[6] = b'\x14'

        channel = stride._event_handler.channel
        channel.process(ChannelBroadcastDataMessage(data=test_data))

        self.assertEqual(20, stride.stride_count)

    def test_receives_page_80_channel_broadcast_message(self):
        stride = Stride(self.node, self.network)

        self.assertEqual(None, stride.hardware_revision)
        self.assertEqual(None, stride.manufacturer_id)
        self.assertEqual(None, stride.model_number)

        test_data = bytearray(b'\x00' * 8)
        test_data[0] = b'\x50'
        test_data[3] = b'\x05'

        test_data[4] = b'\x03'
        test_data[5] = b'\x14'

        test_data[6] = b'\x06'
        test_data[7] = b'\x12'

        channel = stride._event_handler.channel
        channel.process(ChannelBroadcastDataMessage(data=test_data))

        self.assertEqual(5, stride.hardware_revision)
        self.assertEqual(5123, stride.manufacturer_id)
        self.assertEqual(4614, stride.model_number)

    def test_receives_page_81_channel_broadcast_message(self):
        stride = Stride(self.node, self.network)

        self.assertEqual(None, stride.software_revision)
        self.assertEqual(None, stride.serial_number)

        test_data = bytearray(b'\x00' * 8)
        test_data[0] = b'\x51'
        test_data[3] = b'\x02'

        test_data[4] = b'\x04'
        test_data[5] = b'\x12'
        test_data[6] = b'\x15'
        test_data[7] = b'\x07'

        channel = stride._event_handler.channel
        channel.process(ChannelBroadcastDataMessage(data=test_data))

        self.assertEqual(2, stride.software_revision)
        self.assertEqual(68293895, stride.serial_number)
