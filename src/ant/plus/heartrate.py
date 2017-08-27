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

from ant.plus.plus import _EventHandler


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

    def heartrate_data(self, computed_heartrate, rr_interval_ms):
        """Called when heart rate data is received.

        Currently only computed heart rate is returned.
        TODO: R-R interval data.
        """
        pass


class HeartRate(object):
    """ANT+ Heart Rate

    """
    def __init__(self, node, device_id=0, transmission_type=0, callback=None):
        """Open a channel for heart rate data

        Device pairing is performed by using a device_id and transmission_type
        of 0. Once a device has been identified for pairing, a new channel
        should be created for the identified device.
        """
        self._event_handler = _EventHandler(self, node)

        self.callback = callback

        self.lock = Lock()
        self._computed_heart_rate = None
        self._previous_beat_count = 0
        self._previous_event_time = 0

        self._page_toggle_observed = False
        self._page_toggle = None

        self._detected_device = None

        CHANNEL_FREQUENCY = 0x39
        CHANNEL_PERIOD = 8070
        DEVICE_TYPE = 0x78
        SEARCH_TIMEOUT = 30
        self._event_handler.open_channel(CHANNEL_FREQUENCY, CHANNEL_PERIOD,
                                         transmission_type, DEVICE_TYPE,
                                         device_id, SEARCH_TIMEOUT)

    def wraparound_difference(self, current, previous, max_value):
        difference = 0

        if previous > current:
            correction = current + max_value
            difference = correction - previous
        else:
            difference = current - previous

        return difference


    def rr_interval_correction(self, time_difference):
        return time_difference * 1000 / 1024


    def _set_data(self, data):
        # ChannelMessage prepends the channel number to the message data
        # (Incorrectly IMO)
        data_size = 9
        payload_offset = 1
        page_index = 0 + payload_offset
        prev_event_time_lsb_index = 2 + payload_offset
        prev_event_time_msb_index = 3 + payload_offset
        event_time_lsb_index = 4 + payload_offset
        event_time_msb_index = 5 + payload_offset
        heart_beat_count_index = 6 + payload_offset
        computed_heart_rate_index = 7 + payload_offset

        if len(data) != data_size:
            return

        rr_interval = None
        with self.lock:
            self._computed_heart_rate = data[computed_heart_rate_index]

            page = data[page_index] & 0x7f
            page_toggle = data[page_index] >> 7

            if not self._page_toggle_observed:
                if self._page_toggle is None:
                    self._page_toggle = page_toggle
                else:
                    if self._page_toggle != page_toggle:
                        self._page_toggle_observed = True

            beat_count = data[heart_beat_count_index]
            beat_count_difference = self.wraparound_difference(beat_count, self._previous_beat_count, 256)
            self._previous_beat_count = beat_count

            time_difference = None
            if self._page_toggle_observed and page == 4:
                prev_event_time = (data[prev_event_time_msb_index] << 8) + (data[prev_event_time_lsb_index])
                event_time = (data[event_time_msb_index] << 8) + (data[event_time_lsb_index])
                time_difference = self.wraparound_difference(event_time, prev_event_time, 65535)
            elif page == 0:
                event_time = (data[event_time_msb_index] << 8) + (data[event_time_lsb_index])
                if beat_count_difference == 1:
                    time_difference = self.wraparound_difference(event_time, self.previous_event_time, 65535)
                else:
                    time_difference = None

                self.previous_event_time = event_time

            if time_difference is not None:
                rr_interval = self.rr_interval_correction(time_difference)

        if (self.callback):
            heartrate_data = getattr(self.callback, 'heartrate_data', None)
            if heartrate_data:
                heartrate_data(self._computed_heart_rate, rr_interval)

    def _set_detected_device(self, device_num, trans_type):
        with self.lock:
            self._detected_device = (device_num, trans_type)

        if (self.callback):
            device_found = getattr(self.callback, 'device_found', None)
            if device_found:
                device_found(device_num, trans_type)


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
        return self._event_handler._state

    @property
    def channel(self):
        """Temporary until refactoring unit tests.
        """
        return self._event_handler.channel
