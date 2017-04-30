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

from ant.core.node import Network
from ant.core.constants import NETWORK_KEY_ANT_PLUS, NETWORK_NUMBER_PUBLIC, CHANNEL_TYPE_TWOWAY_RECEIVE

class HeartRate:

    def __init__(self, node):
        self.node = node

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

        # Default ID is set up for pairing
        self.channel.setID(0, 0x78, 0)

        self.channel.assign(0, CHANNEL_TYPE_TWOWAY_RECEIVE)

        self.channel.open()



