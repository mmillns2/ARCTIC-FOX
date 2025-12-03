import threading
import socket
import time

from cooldown_loop_dilution_v2 import switch_on, switch_off, heater_on, heater_off

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
        }

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

    # --------------- Remote Functions -----------------
    def handle_cmd(self, cmd_str: str):
        '''
        Parse command of the form: 'cmd_func device_name channel value'
        and call the appropriate function from the dispatch table.
        '''
        parts = cmd_str.strip().split()

        if len(parts) != 4:
            raise ValueError("Command must be: 'cmd_func device_name channel value'")

        cmd_func, device_name, channel, value = parts

        if cmd_func not in self.func_dict:
            raise ValueError(f"Unknown command '{cmd_func}'")
            return "1"

        func = self.func_dict[cmd_func]
        func(device_name, channel, value)
        return "0"

    # -------------- Thread functions ---------------
    def stop(self):
        self.stop_flag.set()

    def run(self):
        '''
        Main loop that listens for commands and processes them.
        '''
        with socket.socket() as s:
            s.bind((self.host, self.port))
            s.listen()

            print("[Client] Ready for commands...")

            while not self.stop_flag.is_set():
                try:
                    s.settimeout(0.1)  # allows checking stop flag
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
