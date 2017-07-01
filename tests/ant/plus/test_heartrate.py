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
import struct

from fakes import *

from ant.core import event, message
from ant.core.constants import NETWORK_KEY_ANT_PLUS, CHANNEL_TYPE_TWOWAY_RECEIVE
from ant.core.node import Network, Node, Channel, Device
from ant.core.message import ChannelBroadcastDataMessage, ChannelIDMessage, ChannelFrequencyMessage, ChannelAssignMessage, ChannelPeriodMessage, ChannelSearchTimeoutMessage, ChannelOpenMessage, ChannelRequestMessage
import ant.core.constants as constants

from ant.plus.heartrate import *
from ant.plus.plus import *

def send_fake_heartrate_msg(hr):
    test_data = bytearray(b'\x00' * 8)
    test_data[6] = 23
    test_data[7] = b'\x64'
    hr.channel.process(ChannelBroadcastDataMessage(data=test_data))


def create_msg(page_number = 0, page_toggle = 0, page_bytes = bytearray(b'\xff' * 3),
               beat_time = 2013, beat_count = 131, computed_hr = 0xb4):
    channel_number = 0
    msg = bytearray(b'\x00' * 9)
    struct.pack_into("<BBBBBHBB", msg, 0, channel_number,
                     page_number | (page_toggle << 7),
                     page_bytes[0], page_bytes[1], page_bytes[2],
                     beat_time, beat_count, computed_hr)

    return msg


class TestHeartRateCallback(HeartRateCallback):
    def __init__(self):
        self.device_number = None
        self.transmission_type = None
        self.computed_heartrate = None

    def device_found(self, device_number, transmission_type):
        self.device_number = device_number
        self.transmission_type = transmission_type

    def heartrate_data(self, computed_heartrate, rr_interval_ms):
        self.computed_heartrate = computed_heartrate
        self.rr_interval_ms = rr_interval_ms


class HeartRateTest(unittest.TestCase):
    def setUp(self):
        self.event_machine = FakeEventMachine()
        self.node = FakeNode(self.event_machine)

    def test_requires_running_node(self):
        self.node.running = False

        with self.assertRaises(Exception):
            hr = HeartRate(self.node)

    def test_requires_available_network(self):
        self.node.networks = []

        with self.assertRaises(Exception):
            hr = HeartRate(self.node)

    def test_node_setup(self):
        hr = HeartRate(self.node)

        self.assertEqual(0, self.node.network_number)
        self.assertEqual(NETWORK_KEY_ANT_PLUS,
                         self.node.network_key)

    def test_requires_free_channel(self):
        self.node.use_all_channels()

        with self.assertRaises(Exception):
            hr = HeartRate(self.node)

    def test_default_channel_setup(self):
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

    def test_paired_channel_setup(self):
        hr = HeartRate(self.node, device_id = 1234, transmission_type = 2)

        device = Device(1234, 0x78, 2)
        self.assertEqual(device.number, hr.channel.device.number)
        self.assertEqual(device.type, hr.channel.device.type)
        self.assertEqual(device.transmissionType,
                         hr.channel.device.transmissionType)

    def test_receives_channel_broadcast_message(self):
        hr = HeartRate(self.node)

        self.assertEqual(None, hr.computed_heart_rate)

        test_data = bytearray(b'\x00' * 8)
        test_data[7] = b'\x64'
        hr.channel.process(ChannelBroadcastDataMessage(data=test_data))

        self.assertEqual(100, hr.computed_heart_rate)

    def test_channel_order_of_operations(self):
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

    def test_unpaired_channel_queries_id(self):
        hr = HeartRate(self.node)

        # This should be higher level, but Node nor Channel provide it
        send_fake_heartrate_msg(hr)

        messages = self.event_machine.messages
        self.assertIsInstance(messages[6], ChannelRequestMessage)
        self.assertEqual(messages[6].messageID, constants.MESSAGE_CHANNEL_ID)

    def test_receives_channel_id_message(self):
        hr = HeartRate(self.node)

        # What should this do if we are connecting to a specific device?
        self.assertEqual(None, hr.detected_device)
        hr.channel.process(ChannelIDMessage(0, 23358, 120, 1))

        self.assertEqual((23358, 1), hr.detected_device)
        self.assertEqual(STATE_RUNNING, hr.state)

    def test_paired_but_undetected_device_queries_id(self):
        hr = HeartRate(self.node, 23358, 1)

        self.assertEqual(None, hr.detected_device)
        send_fake_heartrate_msg(hr)

        messages = self.event_machine.messages
        self.assertIsInstance(messages[6], ChannelRequestMessage)
        self.assertEqual(messages[6].messageID, constants.MESSAGE_CHANNEL_ID)

        hr.channel.process(ChannelIDMessage(0, 23358, 120, 1))
        self.assertEqual((23358, 1), hr.detected_device)
        self.assertEqual(STATE_RUNNING, hr.state)

    def test_channel_search_timeout_and_close(self):
        hr = HeartRate(self.node)

        self.assertEqual(STATE_SEARCHING, hr.state)

        msg = ChannelEventResponseMessage(0x00,
                                          constants.MESSAGE_CHANNEL_EVENT,
                                          constants.EVENT_RX_SEARCH_TIMEOUT)
        hr.channel.process(msg)

        self.assertEqual(STATE_SEARCH_TIMEOUT, hr.state)

        msg = ChannelEventResponseMessage(0x00,
                                          constants.MESSAGE_CHANNEL_EVENT,
                                          constants.EVENT_CHANNEL_CLOSED)
        hr.channel.process(msg)
        self.assertEqual(STATE_CLOSED, hr.state)

    def test_channel_rx_fail_over_to_search(self):
        hr = HeartRate(self.node)

        self.assertEqual(STATE_SEARCHING, hr.state)

        send_fake_heartrate_msg(hr)
        hr.channel.process(ChannelIDMessage(0, 23358, 120, 1))

        self.assertEqual(STATE_RUNNING, hr.state)

        msg = ChannelEventResponseMessage(0x00,
                                          constants.MESSAGE_CHANNEL_EVENT,
                                          constants.EVENT_RX_FAIL_GO_TO_SEARCH)
        hr.channel.process(msg)

        self.assertEqual(STATE_SEARCHING, hr.state)

    def test_device_detected_callback(self):
        callback = TestHeartRateCallback()
        hr = HeartRate(self.node, callback = callback)

        hr.channel.process(ChannelIDMessage(0, 23358, 120, 1))

        self.assertEqual(23358, callback.device_number)
        self.assertEqual(1, callback.transmission_type)

    def test_data_callback(self):
        callback = TestHeartRateCallback()
        hr = HeartRate(self.node, callback = callback)

        send_fake_heartrate_msg(hr)
        self.assertEqual(100, callback.computed_heartrate)

    def test_consecutive_beat_page_0_r_r_interval(self):
        callback = TestHeartRateCallback()
        hr = HeartRate(self.node, callback = callback)

        hr._set_data(create_msg(beat_time = 1672, beat_count = 130, computed_hr = 0xb4))

        hr._set_data(create_msg(beat_time = 2013, beat_count = 131, computed_hr = 0xb4))

        self.assertEqual(333, callback.rr_interval_ms)

    def test_non_consecutive_beat_page_0_r_r_interval(self):
        callback = TestHeartRateCallback()
        hr = HeartRate(self.node, callback = callback)

        hr._set_data(create_msg(beat_time = 1672, beat_count = 130, computed_hr = 0xb4))

        hr._set_data(create_msg(beat_time = 2013, beat_count = 132, computed_hr = 0xb4))

        self.assertEqual(None, callback.rr_interval_ms)


    def test_consecutive_page_0_r_r_interval_wraparound(self):
        callback = TestHeartRateCallback()
        hr = HeartRate(self.node, callback = callback)

        hr._set_data(create_msg(beat_time = 65535, beat_count = 255, computed_hr = 0xb4))
        hr._set_data(create_msg(beat_time = 341, beat_count = 0, computed_hr = 0xb4))

        self.assertEqual(333, callback.rr_interval_ms)

    def test_page_gt_0_ignored_until_toggle_bit_changes(self):
        callback = TestHeartRateCallback()
        hr = HeartRate(self.node, callback = callback)

        page_bytes = bytearray(b'\xff' * 3)
        struct.pack_into("<BH", page_bytes, 0, 0xff, 1672)

        hr._set_data(create_msg(page_number = 4, page_toggle = 0,
                                page_bytes = page_bytes, beat_time = 2013,
                                beat_count = 131, computed_hr = 0xb4))
        self.assertEqual(None, callback.rr_interval_ms)

        hr._set_data(create_msg(page_number = 4, page_toggle = 1,
                                page_bytes = page_bytes, beat_time = 2013,
                                beat_count = 131, computed_hr = 0xb4))
        self.assertEqual(333, callback.rr_interval_ms)

    def test_page_2_and_3_return_None_rr_interval(self):
        callback = TestHeartRateCallback()
        hr = HeartRate(self.node, callback = callback)

        page_bytes = bytearray(b'\xff' * 3)

        hr._set_data(create_msg(page_number = 2, page_toggle = 0,
                                page_bytes = page_bytes, beat_time = 2013,
                                beat_count = 131, computed_hr = 0xb4))
        self.assertEqual(None, callback.rr_interval_ms)

        hr._set_data(create_msg(page_number = 2, page_toggle = 1,
                                page_bytes = page_bytes, beat_time = 2014,
                                beat_count = 132, computed_hr = 0xb4))
        self.assertEqual(None, callback.rr_interval_ms)

        hr._set_data(create_msg(page_number = 3, page_toggle = 0,
                                page_bytes = page_bytes, beat_time = 2015,
                                beat_count = 133, computed_hr = 0xb4))
        self.assertEqual(None, callback.rr_interval_ms)

        hr._set_data(create_msg(page_number = 3, page_toggle = 1,
                                page_bytes = page_bytes, beat_time = 2016,
                                beat_count = 134, computed_hr = 0xb4))
        self.assertEqual(None, callback.rr_interval_ms)

    def test_close_calls_close_on_channel(self):
        callback = TestHeartRateCallback()
        hr = HeartRate(self.node, callback = callback)

        hr.close()
        self.assertEqual(True, hr.channel.close_called)

