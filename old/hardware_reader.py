# hardware_reader.py
import time
import serial
import numpy as np
import serial.tools.list_ports

from CTC100 import CTC100Device
from lakeshore224device import LakeShore224Device
from lakeshore372device import LakeShore372Device

class HardwareTemperatureReader:
    """
    Headless (no GUI) replacement for your TemperaturePlotter.
    Only reads temperatures and returns a unified reading dict.
    """

    def __init__(self, devices):
        self.devices = devices

    def read_temperatures(self):
        d = self.devices
        readings = {}

        # -------------------- CTC100A --------------------
        if "CTC100A" in d:
            dev = d["CTC100A"]
            readings["CTC100A"] = {
                "4switchA": dev.get_temperature("4switch"),
                "4pumpA":   dev.get_temperature("4pump"),
                "3switchA": dev.get_temperature("3switch"),
                "3pumpA":   dev.get_temperature("3pump"),
            }

        # -------------------- CTC100B --------------------
        if "CTC100B" in d:
            dev = d["CTC100B"]
            readings["CTC100B"] = {
                "4switchB": dev.get_temperature("4switch"),
                "4pumpB":   dev.get_temperature("4pump"),
                "3switchB": dev.get_temperature("3switch"),
                "3pumpB":   dev.get_temperature("3pump"),
            }

        # -------------------- LakeShore 224 --------------------
        if "Lakeshore224" in d:
            dev = d["Lakeshore224"]
            readings["Lakeshore224"] = {
                "4HePotA": dev.get_temperature("C1"),
                "3HePotA": dev.get_temperature("B"),
                "4HePotB": dev.get_temperature("C2"),
                "3HePotB": dev.get_temperature("D1"),
                "Condenser": dev.get_temperature("A"),
                "50K Plate": dev.get_temperature("D2"),
                "4K Plate": dev.get_temperature("D3"),
            }

        # -------------------- LakeShore 372 --------------------
        if "Lakeshore372" in d:
            dev = d["Lakeshore372"]
            readings["Lakeshore372"] = {
                "MC":    dev.get_temperature("1"),
                "Still": dev.get_temperature("A"),
            }

        return readings

