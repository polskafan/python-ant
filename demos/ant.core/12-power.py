# -*- coding: utf-8 -*-
"""Demonstrate the use of the ANT+ Power Device Profile
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

def power_data(event_count, pedal_power_ratio, cadence, accumulated_power, instantaneous_power):
    print(f'Power: {instantaneous_power}, accumulated: {accumulated_power}, ratio: {pedal_power_ratio}, cadence: {cadence}')

def torque_and_pedal_data(event_count, left_torque, right_torque, left_pedal_smoothness, right_pedal_smoothness):
    print(f'Torque: {left_torque} (left), {right_torque} (right),  pedal smoothness: {left_pedal_smoothness} (left), {right_pedal_smoothness} (right)')


#-------------------------------------------------#
#  Initialization                                 #
#-------------------------------------------------#
antnode = Node(driver.USB2Driver(log=LOG, debug=DEBUG, idProduct=0x1009))
try:
    antnode.start()
    network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
    antnode.setNetworkKey(NETWORK_NUMBER_PUBLIC, network)
    
    powerMonitor = BicyclePower(antnode, network,
                         {'onDevicePaired': device_paired,
                          'onSearchTimeout': search_timed_out,
                          'onChannelClosed': channel_closed,
                          'onPowerData': power_data,
                          'onTorqueAndPedalData': torque_and_pedal_data})
    powerMonitor.open()
    print('ANT started. Connecting to devices...')
except ANTException as err:
    print(f'Could not start ANT.\n{err}')


while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break

powerMonitor.close()
antnode.stop()
