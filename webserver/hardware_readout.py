import time
import serial
import numpy as np
import serial.tools.list_ports
import threading
from datetime import datetime

from CTC100 import CTC100Device
from lakeshore224device import LakeShore224Device
from lakeshore372device import LakeShore372Device

from sql import SQL 

from controller import hardware_lock

class HardwareTemperatureReader(threading.Thread):
    """
    Headless (no GUI) replacement for your TemperaturePlotter.
    Only reads temperatures and returns a unified reading dict.
    """

    def __init__(self, devices, sql: SQL):
        super().__init__(daemon=True)
        self.devices = devices
        self.sql = sql
        self.interval = 5.0
        self._stop_event = threading.Event()

    def read_temperatures(self):
        d = self.devices
        readings = {}

        with hardware_lock:
            # -------------------- CTC100A --------------------
            if "CTC100A" in d:
                dev = d["CTC100A"]
                readings["CTC100A"] = {
                    "4switchA [K]": dev.get_temperature("4switch"),
                    "4pumpA [K]":   dev.get_temperature("4pump"),
                    "3switchA [K]": dev.get_temperature("3switch"),
                    "3pumpA [K]":   dev.get_temperature("3pump"),
                }

            # -------------------- CTC100B --------------------
            if "CTC100B" in d:
                dev = d["CTC100B"]
                readings["CTC100B"] = {
                    "4switchB [K]": dev.get_temperature("4switch"),
                    "4pumpB [K]":   dev.get_temperature("4pump"),
                    "3switchB [K]": dev.get_temperature("3switch"),
                    "3pumpB [K]":   dev.get_temperature("3pump"),
                }

            # -------------------- LakeShore 224 --------------------
            if "Lakeshore224" in d:
                dev = d["Lakeshore224"]
                readings["Lakeshore224"] = {
                    "4HePotA [K]": dev.get_temperature("C1"),
                    "3HePotA [K]": dev.get_temperature("B"),
                    "4HePotB [K]": dev.get_temperature("C2"),
                    "3HePotB [K]": dev.get_temperature("D1"),
                    "Condenser [K]": dev.get_temperature("A"),
                    "50K [K]": dev.get_temperature("D2"),
                    "4K [K]": dev.get_temperature("D3"),
                }

            # -------------------- LakeShore 372 --------------------
            if "Lakeshore372" in d:
                dev = d["Lakeshore372"]
                readings["Lakeshore372"] = {
                    "MC [K]":    dev.get_temperature("1"),
                    "Still [K]": dev.get_temperature("A"),
                }

        return readings

    def write_temperatures_to_db(self, readings):
        timestamp = datetime.now()

        for device, channel_dict in readings.items():
            for name, value in channel_dict.items():

                # Safety check: ignore Nones or weird values
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    print(f"Skipping invalid value for {name}: {value}")
                    continue

                self.sql.insertSCValueByName(name, value, timestamp)

    def stop(self):
        self._stop_event.set()

    def run(self):
        print("[HardwareReadoutThread] Starting background temperature logging...")

        while not self._stop_event.is_set():
            try:
                readings = self.read_temperatures()
                self.write_temperatures_to_db(readings)
            except Exception as e:
                print("[HardwareReadoutThread] ERROR during read/write:", e)

            # Sleep with interrupt support
            self._stop_event.wait(self.interval)

        print("[HardwareReadoutThread] Stopped.")
