# -*- coding: utf-8 -*-
"""Demonstrate the use of the ANT+ Heart Rate Device Profile

"""

import time

from ant.core import driver
from ant.core.node import Node
from ant.plus.heartrate import *

from config import *

device = driver.USB2Driver(log=LOG, debug=DEBUG)
antnode = Node(device)

antnode.start()

# Unpaired, search:
hr = HeartRate(antnode)

# Paired to a specific device:
#hr = HeartRate(antnode, 23359, 1)
#hr = HeartRate(antnode, 21840, 81)

monitor = None
while True:
    try:
        time.sleep(1)
        if hr.state == STATE_RUNNING:
            print "Computed heart rate: {}".format(hr.computed_heart_rate)
            if monitor is None:
                monitor = hr.detected_device
                print "Detect monitor device number: %d, transmission type: %d" % monitor
        if hr.state == STATE_CLOSED:
            print "Channel closed, exiting."
            break
    except KeyboardInterrupt:
        break

antnode.stop()
