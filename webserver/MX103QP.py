import serial
import time

PORT = "/dev/ttyACM0"   

class MX103QP:
    def __init__(self, port, timeout=1.0):
        self.ser = serial.Serial(
            port=port,
            baudrate=9600,     # ignored for USB, required for RS232
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=timeout
        )

        # Give the PSU time to settle
        time.sleep(0.2)

    # Low-level helpers
    def _write(self, cmd: str):
        full = cmd.strip() + "\n"
        self.ser.write(full.encode("ascii"))

    def _query(self, cmd: str) -> str:
        self._write(cmd)
        time.sleep(0.05)
        resp = self.ser.read_until(b"\n")
        return resp.decode("ascii").strip()

    # Common commands
    def idn(self) -> str:
        return self._query("*IDN?")

    def reset(self):
        self._write("*RST")

    def lock(self):
        self._write("IFLOCK 1")

    def unlock(self):
        self._write("IFLOCK 0")

    # Output control
    def set_voltage(self, ch: int, volts: float):
        self._write(f"V{ch} {volts}")

    def set_current(self, ch: int, amps: float):
        self._write(f"I{ch} {amps}")

    def output_on(self, ch: int):
        self._write(f"OP{ch} 1")

    def output_off(self, ch: int):
        self._write(f"OP{ch} 0")

    def output_state(self, ch: int) -> bool:
        return bool(int(self._query(f"OP{ch}?")))

    # Readout
    def read_voltage(self, ch: int) -> float:
        resp = self._query(f"V{ch}O?")
        return float(resp.replace("V", ""))

    def read_current(self, ch: int) -> float:
        resp = self._query(f"I{ch}O?")
        return float(resp.replace("A", ""))

    # Cleanup
    def close(self):
        self.ser.close()

