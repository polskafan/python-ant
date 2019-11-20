# -*- coding: utf-8 -*-
"""Demonstrate the use of the ANT+ Heart Rate Device Profile

"""

import time

from ant.core import driver
from ant.core.node import Node, Network, ChannelID
from ant.core.constants import NETWORK_KEY_ANT_PLUS, NETWORK_NUMBER_PUBLIC
from ant.plus.heartrate import *

from config import *


#-------------------------------------------------#
#  ANT Callbacks                                  #
#-------------------------------------------------#
def device_paired(device_profile, channel_id):
    print(f'Connected to {device_profile.name} ({channel_id.deviceNumber})')

def search_timed_out(device_profile):
    print(f'Could not connect to {device_profile.name}')

def channel_closed(device_profile):
    print(f'Channel closed for {device_profile.name}')

def heart_rate_data(computed_heartrate, event_time_ms, rr_interval_ms):
    print(f'Heart rate: {computed_heartrate}, event time(ms): {event_time_ms}, rr interval (ms): {rr_interval_ms}')


#-------------------------------------------------#
#  Initialization                                 #
#-------------------------------------------------#
antnode = Node(driver.USB2Driver(log=LOG, debug=DEBUG, idProduct=0x1009))
try:
    antnode.start()
    network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
    antnode.setNetworkKey(NETWORK_NUMBER_PUBLIC, network)
    
    heartRateMonitor = HeartRate(antnode, network,
                         {'onDevicePaired': device_paired,
                          'onSearchTimeout': search_timed_out,
                          'onChannelClosed': channel_closed,
                          'onHeartRateData': heart_rate_data})
    # Unpaired, search:
    heartRateMonitor.open()

    # Paired to a specific device:
    #heartRateMonitor.open(channel_id(xxx, xxx, xxx))
    
    print('ANT started. Connecting to devices...')
except ANTException as err:
    print(f'Could not start ANT.\n{err}')


while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break

hr.close()
antnode.stop()
