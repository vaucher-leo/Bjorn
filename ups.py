#ups.py
# Description:
# This file, ups.py, is the library that manages the ups-lite battery pack.
#
# Key functionalities include:
# - Reading battery capacity
# - Reading battery voltage
# - Reading if the power adapter is pluged in or not

import struct
import smbus
import sys
import time
import logging
# import RPi.GPIO as GPIO
import gpiozero
from logger import Logger

CW2015_ADDRESS = 0X62
CW2015_REG_VCELL = 0X02
CW2015_REG_SOC = 0X04
CW2015_REG_MODE = 0X0A

class UPS:
    def __init__(self):
        """Initialize the ups connection and get first data"""
        self.logger = Logger(name="ups.py", level=logging.DEBUG)

        # GPIO.setmode(GPIO.BCM)
        # GPIO.setwarnings(False)
        # GPIO.setup(4,GPIO.IN) # GPIO4 is used to detect whether an external power supply is inserted
        self.GPIO_PLUGGED_IN = gpiozero.Button(4, pull_up = False)

        self.battery_capacity = 0.0
        self.voltage = 0.0
        self.plugged_in = False

        try:
            self.bus = smbus.SMBus(1) # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (portI2C1)
        
            # wake up the CW2015 and make a quick-start fuel-gauge calculations
            self.bus.write_word_data(CW2015_ADDRESS, CW2015_REG_MODE, 0x30)

            # Run first measurement
            self.read_capacity()
            self.read_plugged_in()
        except Exception as e:
            self.logger.error(f"Error during ups initialization: {e}")
            raise

    def read_capacity(self):
        """Read battery capacity"""
        read = self.bus.read_word_data(CW2015_ADDRESS, CW2015_REG_SOC)
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        self.battery_capacity = swapped/256
    
    def read_voltage(self):
        """Read battery voltage"""
        read = self.bus.read_word_data(CW2015_ADDRESS, CW2015_REG_VCELL)
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        self.voltage = swapped * 0.305 /1000

    def read_plugged_in(self):
        """Read if power adapter is plugged in or not"""
        #GPIO is high when power is plugged in
        # if (GPIO.input(4) == GPIO.HIGH):
        #     self.plugged_in = True
        # if (GPIO.input(4) == GPIO.LOW):
        #     self.plugged_in = False
        if self.GPIO_PLUGGED_IN.value == 1:
            self.plugged_in = True
        else:
            self.plugged_in = False
    
    def update_all(self):
        """Read all informations"""
        self.read_capacity()
        self.read_voltage()
        self.read_plugged_in()

if __name__ == "__main__":
    try:
         ups = UPS()
    except Exception as e:
        sys.exit(1)