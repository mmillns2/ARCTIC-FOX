import threading
import socket
import time
import json
from cooldown_loop_dilution_v2 import switch_on, switch_off, heater_on, heater_off
from device import get_channels_for_device

# If your real device_lock exists, import it.
# Otherwise assign a new lock:
try:
    from devices.device import device_lock as hardware_lock
except ImportError:
    hardware_lock = threading.Lock()

class DeviceControllerClient(threading.Thread):
    def __init__(self, devices: dict, host: str, port: int):
        super().__init__(daemon=True)
        self.devices = devices
        self.host = host
        self.port = port
        self.stop_flag = threading.Event()

        self.func_dict = {
            "set_switch_voltage": self.set_switch_voltage,
            "turn_off_switch": self.turn_off_switch,
            "set_heater_temperature": self.set_heater_temperature,
            "turn_off_heater": self.turn_off_heater,
            "toggle_heater": self.toggle_heater,
            "set_still_percentage": self.set_still_percentage,
            "turn_off_still": self.turn_off_still,
            "get_devices": self.get_devices,
        }

    # ---------------- Switch Commands ----------------
    def set_switch_voltage(self, device_name, channel, voltage):
        device = self.devices[device_name]
        with hardware_lock:
            switch_on(device, channel, voltage)

    def turn_off_switch(self, device_name, channel, _):
        device = self.devices[device_name]
        with hardware_lock:
            switch_off(device, channel)

    # ---------------- Heater Commands ----------------
    def set_heater_temperature(self, device_name, channel, temperature):
        device = self.devices[device_name]
        with hardware_lock:
            device.write_setpoint(channel, temperature)
            heater_on(device, channel)

    def turn_off_heater(self, device_name, channel, _):
        device = self.devices[device_name]
        with hardware_lock:
            heater_off(device, channel)

    def toggle_heater(self, device_name, channel, state):
        device = self.devices[device_name]
        with hardware_lock:
            if state == "1":
                heater_on(device, channel)
            else:
                heater_off(device, channel)

    # ---------------- Still Heater ----------------
    def set_still_percentage(self, device_name, channel, percent):
        device = self.devices[device_name]
        with hardware_lock:
            device.set_still_voltage(percent)

    def turn_off_still(self, device_name, channel, _):
        device = self.devices[device_name]
        with hardware_lock:
            device.set_still_voltage(0)

    # ---------------- Device List ----------------
    def get_devices(self, *_ignored):
        result = {}
        for name, dev in self.devices.items():
            result[name] = {
                "name": name,
                "channels": get_channels_for_device(name),
            }
        return json.dumps(result)

    # --------------- Command Dispatch ---------------
    def handle_cmd(self, cmd_str: str):
        parts = cmd_str.strip().split()
        cmd_func = parts[0]

        if cmd_func not in self.func_dict:
            print(f"[Client] Unknown command: {cmd_func}")
            return "1"

        func = self.func_dict[cmd_func]

        # Special-case: get_devices takes no args
        if cmd_func == "get_devices":
            return func()

        if len(parts) != 4:
            print("[Client] Invalid command format")
            return "1"

        device_name, channel, value = parts[1:]
        if value != "_":
            value = float(value)
        func(device_name, channel, value)

        return "0"

    # --------------- Thread Loop ----------------
    def run(self):
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print("[Client] Ready for commands...")

            while not self.stop_flag.is_set():
                try:
                    s.settimeout(0.1)
                    conn, addr = s.accept()
                except socket.timeout:
                    continue

                with conn:
                    cmd = conn.recv(1024).decode("ascii")
                    print("[Client] Received:", cmd)
                    try:
                        result = self.handle_cmd(cmd)
                    except Exception as e:
                        print(f"[Client] ERROR: {e}")
                        result = "1"
                    conn.sendall(result.encode("ascii"))

