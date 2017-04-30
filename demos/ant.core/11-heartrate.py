# -*- coding: utf-8 -*-
"""Demonstrate the use of the ANT+ Heart Rate Device Profile

"""

import time

from ant.core import driver
from ant.core.node import Node
from ant.plus.heartrate import HeartRate

from config import *

device = driver.USB2Driver(log=LOG, debug=DEBUG)
antnode = Node(device)

antnode.start()

hr = HeartRate(antnode)

while True:
    try:
        time.sleep(1)
        print hr.computed_heart_rate
    except KeyboardInterrupt:
        break

antnode.stop()
