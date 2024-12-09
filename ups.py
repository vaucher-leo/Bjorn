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

import logging
import struct
import sys
from abc import ABC, abstractmethod

import gpiozero
import smbus

from logger import Logger


def CreateUPS(ups_model):
    """This function is used to create the ups device based on model name"""

    match ups_model:
        case "ups-lite_V1.3":
            return UPS_Lite()
        case "pisugar3":
            return PiSugar3()
        case "pisugar2":
            return PiSugar2()
        case "pisugar2_pro":
            return PiSugar2Pro()
        case _:
            return None


class UPS(ABC):
    """Base class for UPS devices"""
    def __init__(self) -> None:
        """Initialize the ups connection and get first data"""
        self.logger = Logger(name="ups.py", level=logging.DEBUG)

        self.battery_capacity = 0.0
        self.voltage = 0.0
        self.plugged_in = False

    @abstractmethod
    def read_capacity(self) -> bool:
        """Read battery capacity

        Returns:
            bool: True if the value changed
        """
        pass

    @abstractmethod
    def read_voltage(self) -> bool:
        """Read battery voltage

        Returns:
            bool: True if the value changed
        """
        pass

    @abstractmethod
    def read_plugged_in(self) -> bool:
        """Read if power adapter is plugged in or not

        Returns:
            bool: True if the value changed
        """
        pass

    @abstractmethod
    def update_all(self) -> bool:
        """Read all informations and returns if something changed

        Returns:
            bool: True if any value changed
        """
        pass

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

    def read_capacity(self) -> bool:
        """Read battery capacity"""
        read = self.bus.read_word_data(self.i2c_address, self.i2c_regs['CW2015_REG_SOC'])
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        capacity = swapped/256
        ret = self.battery_capacity == capacity
        self.battery_capacity = capacity
        return ret

    def read_voltage(self) -> bool:
        """Read battery voltage"""
        read = self.bus.read_word_data(self.i2c_address, self.i2c_regs['CW2015_REG_VCELL'])
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        voltage = swapped * 0.305 /1000
        ret = self.voltage == voltage
        self.voltage = voltage
        return ret

    def read_plugged_in(self) -> bool:
        """Read if power adapter is plugged in or not"""
        pin_state = bool(self.gpio_plugged_in.value)
        ret = self.plugged_in == pin_state
        self.plugged_in = pin_state
        return ret

    def update_all(self) -> bool:
        """Read all informations and returns if something changed"""
        ret = False
        ret |= self.read_capacity()
        ret |= self.read_voltage()
        ret |= self.read_plugged_in()
        return ret

class PiSugar2(UPS):
    """Class for UPS model: PiSugar2 (IP5209)"""
    # WARNING: Not the same as PiSugar2 Pro!
    # Based on doc from:
    # https://github.com/PiSugar/PiSugar/wiki/PiSugar-2-(Pro)-I2C-Manual

    def __init__(self):
        super().__init__()
        self.i2c_address = 0x75
        self.i2c_regs = {
            "PISUGAR_REG_VCELL_MSB": 0xa2,
            "PISUGAR_REG_VCELL_LSB": 0xa3,
            "PISUGAR_REG_BATT_CAPACITY": 0x2A,
            "PISUGAR_REG_PLUGGED_IN": 0x54
        }

        try:
            self.bus = smbus.SMBus(1) # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (portI2C1)

            # Need to configure registers in order to detect charging status
            self.bus.write_byte_data(self.i2c_address, 0x51, 0x2) # Set Vset to internal register
            reg = self.bus.read_byte_data(self.i2c_address, 0x52)
            self.bus.write_byte_data(self.i2c_address, 0x52, reg | 0x10) # Set function of GPIO4
            reg = self.bus.read_byte_data(self.i2c_address, 0x53)
            self.bus.write_byte_data(self.i2c_address, 0x53, reg | 0x10) # Enable charging on GPIO4

            # Run first measurement
            self.update_all()

        except Exception as e:
            self.logger.error(f"Error during PiSugar3 initialization: {e}")
            raise

    def read_capacity(self) -> bool:
        """Read battery capacity"""
        # Thanx to this repo:
        # https://github.com/kellertk/pwnagotchi-plugin-pisugar2/blob/main/pisugar2.py

        battery_curve = [
            [4.16, 5.5, 100, 100],
            [4.05, 4.16, 87.5, 100],
            [4.00, 4.05, 75, 87.5],
            [3.92, 4.00, 62.5, 75],
            [3.86, 3.92, 50, 62.5],
            [3.79, 3.86, 37.5, 50],
            [3.66, 3.79, 25, 37.5],
            [3.52, 3.66, 12.5, 25],
            [3.49, 3.52, 6.2, 12.5],
            [3.1, 3.49, 0, 6.2],
            [0, 3.1, 0, 0],
        ]
        capacity = 0
        battery_v = self.voltage
        for range in battery_curve:
            if range[0] < battery_v <= range[1]:
                level_base = ((battery_v - range[0]) / (range[1] - range[0])) * (range[3] - range[2])
                capacity = level_base + range[2]
        ret = self.battery_capacity == capacity
        self.battery_capacity = capacity
        return ret

    def read_voltage(self) -> bool:
        """Read battery voltage"""
        read = self.bus.read_i2c_block_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_VCELL_MSB'], 2)
        voltage_raw = (((read[1]&0x3F) << 8) | read[0])
        voltage = (2600.0 - voltage_raw * 0.26855) / 1000
        ret = self.voltage == voltage
        self.voltage = voltage
        return ret

    def read_plugged_in(self) -> bool:
        """Read if power adapter is plugged in or not"""
        read = self.bus.read_byte_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_PLUGGED_IN'])
        plugged_in = bool((read >> 4)&0x01)
        ret = self.plugged_in == plugged_in
        self.plugged_in = plugged_in
        return ret

    def update_all(self) -> bool:
        """Read all informations and returns if something changed"""
        ret = False
        ret |= self.read_capacity()
        ret |= self.read_voltage()
        ret |= self.read_plugged_in()
        return ret

class PiSugar2Pro(UPS):
    """Class for UPS model: PiSugar2Pro (IP5312)"""
    # WARNING: Not the same as PiSugar2 Pro!
    # Based on doc from:
    # https://github.com/PiSugar/PiSugar/wiki/PiSugar-2-(Pro)-I2C-Manual

    def __init__(self):
        super().__init__()
        self.i2c_address = 0x75
        self.i2c_regs = {
            "PISUGAR_REG_VCELL_MSB": 0xd0,
            "PISUGAR_REG_VCELL_LSB": 0xd1,
            "PISUGAR_REG_BATT_CAPACITY": 0x2A,
            "PISUGAR_REG_PLUGGED_IN": 0xDC
        }

        try:
            self.bus = smbus.SMBus(1) # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (portI2C1)

            # Need to configure registers in order to detect charging status
            ret = self.bus.read_byte_data(self.i2c_address, 0x29)
            self.bus.write_byte_data(self.i2c_address, 0x51, ret | 0x40) # Set Vset to internal register
            reg = self.bus.read_byte_data(self.i2c_address, 0x52)
            self.bus.write_byte_data(self.i2c_address, 0x52, (reg | 0x40) & ~0x20) # Set function of GPIO4
            self.bus.write_byte_data(self.i2c_address, 0xC2, 0x00) # Enable charging

            # Run first measurement
            self.update_all()

        except Exception as e:
            self.logger.error(f"Error during PiSugar3 initialization: {e}")
            raise

    def read_capacity(self) -> bool:
        """Read battery capacity"""
        # Thanx to this repo:
        # https://github.com/kellertk/pwnagotchi-plugin-pisugar2/blob/main/pisugar2.py

        battery_curve = [
            [4.16, 5.5, 100, 100],
            [4.05, 4.16, 87.5, 100],
            [4.00, 4.05, 75, 87.5],
            [3.92, 4.00, 62.5, 75],
            [3.86, 3.92, 50, 62.5],
            [3.79, 3.86, 37.5, 50],
            [3.66, 3.79, 25, 37.5],
            [3.52, 3.66, 12.5, 25],
            [3.49, 3.52, 6.2, 12.5],
            [3.1, 3.49, 0, 6.2],
            [0, 3.1, 0, 0],
        ]
        capacity = 0
        battery_v = self.voltage
        for range in battery_curve:
            if range[0] < battery_v <= range[1]:
                level_base = ((battery_v - range[0]) / (range[1] - range[0])) * (range[3] - range[2])
                capacity = level_base + range[2]
        ret = self.battery_capacity == capacity
        self.battery_capacity = capacity
        return ret

    def read_voltage(self) -> bool:
        """Read battery voltage"""
        read = self.bus.read_i2c_block_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_VCELL_MSB'], 2)
        voltage_raw = (((read[1]&0x3F) << 8) | read[0])
        voltage = (2600.0 - voltage_raw * 0.26855) / 1000
        ret = self.voltage == voltage
        self.voltage = voltage
        return ret

    def read_plugged_in(self) -> bool:
        """Read if power adapter is plugged in or not"""
        read = self.bus.read_i2c_block_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_PLUGGED_IN'], 2)
        if (read[0] == 0xFF) and ((read[1]&0x1F) == 0x1F):
            plugged_in = True
        else:
            plugged_in = False
        ret = self.plugged_in == plugged_in
        self.plugged_in = plugged_in
        return ret

    def update_all(self) -> bool:
        """Read all informations and returns if something changed"""
        ret = False
        ret |= self.read_capacity()
        ret |= self.read_voltage()
        ret |= self.read_plugged_in()
        return ret

class PiSugar3(UPS):
    """Class for UPS model: PiSugar3"""
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

    def read_capacity(self) -> bool:
        """Read battery capacity"""
        capacity = self.bus.read_byte_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_BATT_CAPACITY'])
        ret = self.battery_capacity == capacity
        self.battery_capacity = capacity
        return ret

    def read_voltage(self) -> bool:
        """Read battery voltage"""
        read = self.bus.read_i2c_block_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_VCELL_MSB'], 2)
        voltage = ((read[0] << 8) | read[1])/1000.0
        ret = self.voltage == voltage
        self.voltage = voltage
        return ret

    def read_plugged_in(self) -> bool:
        """Read if power adapter is plugged in or not"""
        read = self.bus.read_byte_data(self.i2c_address, self.i2c_regs['PISUGAR_REG_PLUGGED_IN'])
        plugged_in = bool((read >> 7)&0x01)
        ret = self.plugged_in == plugged_in
        self.plugged_in = plugged_in
        return ret

    def update_all(self) -> bool:
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
        print(f"Exception error: {e}")
        sys.exit(1)
