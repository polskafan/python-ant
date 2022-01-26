# -*- coding: utf-8 -*-
'''
Data processed
     Data Page 16
          Instantaneous speed 0.001 m/s
     Data Page 25
          Instantaneous Cadence spm
          Instantaneous power watts
'''

import time
import subprocess
import os
import fcntl
import sys

from ant.core import driver
from ant.core.node import Node, Network, ChannelID
from ant.core.constants import NETWORK_KEY_ANT_PLUS, NETWORK_NUMBER_PUBLIC
from ant.plus.bikeTrainer import *
from ant.core.resetUSB import reset_USB_Device
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

def bike_Trainer(elapsedTime, distanceTraveled, instantaneousSpeed, kmSpeed, cadence, power):
    print("Speed Km/h {} Cadence {} Power {}".format(str(kmSpeed), str(cadence), str(power)))
    print("#########################################################")


#-------------------------------------------------#
#  Initialization                                 #
#-------------------------------------------------#

try:
    reset_USB_Device()
except Exception as ex:
   print(ex)


antnode = Node(driver.USB2Driver(log=LOG, debug=DEBUG, idProduct=0x1008))
try:
    antnode.start()
    network = Network(key=NETWORK_KEY_ANT_PLUS, name='N:ANT+')
    antnode.setNetworkKey(NETWORK_NUMBER_PUBLIC, network)
    myTrainer = bikeTrainer(antnode, network,
             {'onDevicePaired' : device_paired,
              'onSearchTimeout': search_timed_out,
              'onChannelClosed': channel_closed,
              'onBikeTrainer'  : bike_Trainer})
    # Unpaired, search:
    myTrainer.open()
    print('ANT started. Connecting to devices...')
except ANTException as err:
    print(f'Could not start ANT.\n{err}')

#######################################################################################

while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        break

myTrainer.close()
antnode.stop()
