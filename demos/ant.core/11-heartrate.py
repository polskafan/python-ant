# -*- coding: utf-8 -*-
"""Demonstrate the use of the ANT+ Heart Rate Device Profile

"""

import time

from ant.core import driver
from ant.core.node import Node
from ant.plus.heartrate import *

from config import *

device = driver.USB2Driver(log=LOG, debug=DEBUG, idProduct=0x1009)
antnode = Node(device)

antnode.start()

class DemoHeartRateCallback(HeartRateCallback):
    def __init__(self):
        pass

    def device_found(self, device_number, transmission_type):
        print "Detect monitor device number: %d, transmission type: %d" % (device_number, transmission_type)

    def heartrate_data(self, computed_heartrate, event_time_ms, rr_interval_ms):
        if rr_interval_ms is not None:
            print "Heart rate: %d, event time(ms): %d, rr interval (ms): %d" % (computed_heartrate, event_time_ms, rr_interval_ms)
        else:
            print "Heart rate: %d" % (computed_heartrate, )

callback = DemoHeartRateCallback()
# Unpaired, search:
hr = HeartRate(antnode, callback = callback)

# Paired to a specific device:
#hr = HeartRate(antnode, 23359, 1, callback = callback)
#hr = HeartRate(antnode, 21840, 81, callback = callback)

monitor = None
while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break

hr.close()
antnode.stop()
