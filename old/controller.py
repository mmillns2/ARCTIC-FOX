# controller.py (inside webserver/)
import threading

from cooldown_loop_dilution_v2 import switch_on, switch_off, heater_on, heater_off

# If your real device_lock exists, import it.
# Otherwise assign a new lock:
try:
    from devices.device import device_lock as hardware_lock
except ImportError:
    hardware_lock = threading.Lock()

class DeviceController:
    def __init__(self, devices: dict):
        self.devices = devices

    # ---------------- Switch Functions ----------------
    def set_switch_voltage(self, device_name, channel, voltage):
        device = self.devices[device_name]
        with hardware_lock:
            switch_on(device, channel, voltage)

    def turn_off_switch(self, device_name, channel):
        device = self.devices[device_name]
        with hardware_lock:
            switch_off(device, channel)

    # ---------------- Heater Functions ----------------
    def set_heater_temperature(self, device_name, channel, temperature):
        device = self.devices[device_name]
        with hardware_lock:
            device.write_setpoint(channel, temperature)
            heater_on(device, channel)

    def turn_off_heater(self, device_name, channel):
        device = self.devices[device_name]
        with hardware_lock:
            heater_off(device, channel)

    def toggle_heater(self, device_name, channel, state: bool):
        device = self.devices[device_name]
        with hardware_lock:
            if state:
                heater_on(device, channel)
            else:
                heater_off(device, channel)

    # ---------------- Still Heater Functions ----------------
    def set_still_percentage(self, device_name, channel, percent):
        device = self.devices[device_name]
        with hardware_lock:
            device.set_still_voltage(percent)

    def turn_off_still(self, device_name, channel):
        device = self.devices[device_name]
        with hardware_lock:
            device.set_still_voltage(0)

