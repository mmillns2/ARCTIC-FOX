'''
The N5700 USB port is a USBTMC (USB Test & Measurement Class) device, NOT a
virtual serial/COM port. pyserial CANNOT talk to it. This driver uses PyVISA
with the pure-Python pyvisa-py backend (good for a Raspberry Pi).

Setup on Raspberry Pi:
    sudo apt install libusb-1.0-0
    pip install pyvisa pyvisa-py pyusb psutil zeroconf

echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0957", ATTRS{idProduct}=="0807", MODE="0660", GROUP="plugdev"' | sudo tee /etc/udev/rules.d/99-n5700.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
groups | grep -q plugdev || sudo usermod -aG plugdev $USER
'''

import time
import pyvisa


class N5745A:
    def __init__(self, resource=None, timeout=5000, name=None):
        '''
        resource : VISA resource string, e.g.
                   'USB0::0x0957::0x0807::MY5745XXXXX::0::INSTR'.
                   If None, the first USB INSTR resource found is used.
        timeout  : I/O timeout in milliseconds.
        '''
        self.rm = pyvisa.ResourceManager("@py")  # pyvisa-py backend

        if resource is None:
            resource = self._autodetect()

        self.inst = self.rm.open_resource(resource)
        self.inst.timeout = timeout
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"
        self.name = name

        print(f"Connected to N5745A on {resource}")
        # Give the PSU time to settle
        time.sleep(0.2)
        self.output_on()
        time.sleep(0.2)

    def _autodetect(self) -> str:
        resources = [
            r for r in self.rm.list_resources()
            if r.upper().startswith("USB") and "::INSTR" in r.upper()
        ]
        if not resources:
            raise RuntimeError(
                "No USB VISA instrument found. Check the cable, that the PSU is "
                "powered on, and your udev rules / permissions."
            )
        return resources[0]

    def _write(self, cmd: str):
        """Send a command."""
        self.inst.write(cmd.strip())

    def _query(self, cmd: str) -> str:
        """Send a query and read the reply."""
        return self.inst.query(cmd.strip()).strip()

    def idn(self) -> str:
        """Returns power supply information."""
        return self._query("*IDN?")

    def status(self) -> int:
        """Returns the status byte (*STB?) as int."""
        return int(self._query("*STB?"))

    def error(self) -> str:
        """Returns the next error from the error queue."""
        return self._query("SYST:ERR?")

    # Output on/off
    def output_on(self):
        self._write("OUTP ON")

    def output_off(self):
        self._write("OUTP OFF")

    # Output control (ch is ignored - N5745A is single-output)
    def set_voltage(self, ch: int, volts: float):
        self._write(f"VOLT {volts:.3f}")

    def set_current(self, ch: int, amps: float):
        self._write(f"CURR {amps:.3f}")

    def get_voltage_setpoint(self, ch: int) -> float:
        return float(self._query("VOLT?"))

    def get_current_setpoint(self, ch: int) -> float:
        return float(self._query("CURR?"))

    # Read actual output values
    def get_voltage(self, ch: int) -> float:
        return float(self._query("MEAS:VOLT?"))

    def get_current(self, ch: int) -> float:
        return float(self._query("MEAS:CURR?"))

    def close(self):
        try:
            self.output_off()
        finally:
            self.inst.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
