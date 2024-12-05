#ups.py
# Description:
# This file, ups.py, is the library that manages the ups-lite battery pack.
#
# Key functionalities include:
# - Reading battery capacity
# - Reading battery voltage
# - Reading if the power adapter is pluged in or not
#
# Supported UPS:
# - UPS-Lite_V1.3
# - PiSugar3
#

import struct
import smbus
import sys
import time
import logging
import gpiozero
from logger import Logger

def CreateUPS(ups_model):
    """This function is used to create the ups device based on model name"""

    match ups_model:
        case "ups-lite_V1.3":
            return UPS_Lite()
        case "pisugar3":
            return PiSugar3()
        case _:
            return UPS()


class UPS:
    """Base class for UPS devices"""
    def __init__(self) -> None:
        """Initialize the ups connection and get first data"""
        self.logger = Logger(name="ups.py", level=logging.DEBUG)

        self.battery_capacity = 0.0
        self.voltage = 0.0
        self.plugged_in = False

    def read_capacity(self) -> None:
        """Read battery capacity"""
        self.battery_capacity = None

    def read_voltage(self) -> None:
        """Read battery voltage"""
        self.voltage = None

    def read_plugged_in(self) -> None:
        """Read if power adapter is plugged in or not"""
        self.plugged_in = False

    def update_all(self) -> None:
        """Read all informations and returns if something changed"""
        self.read_capacity()
        self.read_voltage()
        self.read_plugged_in()
        return Flase

class UPS_Lite(UPS):
    """Class for UPS model: UPS-Lite_V1.3"""
    def __init__(self):
        super().__init__()
        self.i2c_address = 0x62
        self.i2c_regs = {
            "CW2015_REG_VCELL": 0x02,
            "CW2015_REG_SOC": 0x04,
            "CW2015_REG_MODE": 0x0A
        }
        # Plug in detection is done by reading a gpio
        self.gpio_plugged_in = gpiozero.Button(4, pull_up = False)

        try:
            self.bus = smbus.SMBus(1) # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (portI2C1)

            # wake up the CW2015 and make a quick-start fuel-gauge calculations
            self.bus.write_word_data(self.i2c_address, self.i2c_regs['CW2015_REG_MODE'], 0x30)

            # Run first measurement
            self.update_all()

        except Exception as e:
            self.logger.error(f"Error during ups_lite initialization: {e}")
            raise

    def read_capacity(self):
        """Read battery capacity"""
        read = self.bus.read_word_data(self.i2c_address, self.i2c_regs['CW2015_REG_SOC'])
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        capacity = swapped/256
        ret = self.battery_capacity == capacity
        self.battery_capacity = capacity
        return ret

    def read_voltage(self):
        """Read battery voltage"""
        read = self.bus.read_word_data(self.i2c_address, self.i2c_regs['CW2015_REG_VCELL'])
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        voltage = swapped * 0.305 /1000
        ret = self.voltage == voltage
        self.voltage = voltage
        return ret

    def read_plugged_in(self):
        """Read if power adapter is plugged in or not"""
        pin_state = bool(self.gpio_plugged_in.value)
        ret = self.plugged_in == pin_state
        self.plugged_in = pin_state
        return ret

    def update_all(self):
        """Read all informations and returns if something changed"""
        ret = False
        ret |= self.read_capacity()
        ret |= self.read_voltage()
        ret |= self.read_plugged_in()
        return ret

class PiSugar3(UPS):
    """Class for UPS model: UPS-Lite_V1.3"""
    def __init__(self):
        super().__init__()
        self.i2c_address = 0x57 # Default value, can be changed by user
        self.i2c_regs = {
            "PISUGAR_REG_VCELL_MSB": 0x22,
            "PISUGAR_REG_VCELL_LSB": 0x23,
            "PISUGAR_REG_BATT_CAPACITY": 0x2A,
            "PISUGAR_REG_PLUGGED_IN": 0x02
        }

        try:
            self.bus = smbus.SMBus(1) # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (portI2C1)

            # Run first measurement
            self.update_all()

        except Exception as e:
            self.logger.error(f"Error during PiSugar3 initialization: {e}")
            raise

    def read_capacity(self):
        """Read battery capacity"""
        capacity = self.bus.read_byte_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_BATT_CAPACITY'])
        ret = self.battery_capacity == capacity
        self.battery_capacity = capacity
        return ret

    def read_voltage(self):
        """Read battery voltage"""
        read = self.bus.read_i2c_block_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_VCELL_MSB'], 2)
        voltage = ((read[0] << 8) | read[1])/1000.0
        ret = self.voltage == voltage
        self.voltage = voltage
        return ret

    def read_plugged_in(self):
        """Read if power adapter is plugged in or not"""
        read = self.bus.read_byte_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_PLUGGED_IN'])
        plugged_in = bool((read >> 7)&0x01)
        ret = self.plugged_in == plugged_in
        self.plugged_in = pin_state
        return ret

    def update_all(self):
        """Read all informations and returns if something changed"""
        ret = False
        ret |= self.read_capacity()
        ret |= self.read_voltage()
        ret |= self.read_plugged_in()
        return ret

if __name__ == "__main__":
    try:
         ups = UPS_Lite()
    except Exception as e:
        sys.exit(1)
