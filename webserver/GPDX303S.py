import serial
import time

PORT = "/dev/ttyUSB0"

class GPDX303S:
    def __init__(self, port, baudrate=9600, timeout=1.0, name=None):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=timeout,
        )
        
        print(f"Connected to GPDX303S power supply on {port}")

        # Give the PSU time to settle
        time.sleep(0.2)
        self.output_on()
        time.sleep(0.2)

    # Low-level helpers
    def _write(self, cmd: str):
        '''
        Send a command (LF terminated)
        '''
        full = cmd.strip() + "\n"
        self.ser.write(full.encode("ascii"))

    def _query(self, cmd: str) -> str:
        '''
        Send a query (CR terminated) and read reply
        '''
        full = cmd.strip() + "\r"
        self.ser.write(full.encode("ascii"))
        time.sleep(0.05)
        resp = self.ser.read_until(b"\n")
        return resp.decode("ascii").strip()

    # Common commands
    def idn(self) -> str:
        '''
        Returns power supply information.
        '''
        return self._query("*IDN?")

    def status(self) -> int:
        '''
        Returns raw STATUS? byte as int
        '''
        return int(self._query("STATUS?"))

    def error(self) -> str:
        '''
        Returns current error.
        '''
        return self._query("ERR?")

    # Readout
    def output_on(self):
        self._write("OUT1")

    def output_off(self):
        self._write("OUT0")

    # Output control
    def set_voltage(self, ch: int, volts: float):
        self._write(f"VSET{ch}:{volts:.3f}")

    def set_current(self, ch: int, amps: float):
        self._write(f"ISET{ch}:{amps:.3f}")

    def get_voltage_setpoint(self, ch: int) -> float:
        return float(self._query(f"VSET{ch}?").replace('V', ''))

    def get_current_setpoint(self, ch: int) -> float:
        return float(self._query(f"ISET{ch}?").replace('A', ''))

    # Read actual output values
    def get_voltage(self, ch: int) -> float:
        return float(self._query(f"VOUT{ch}?").replace('V', ''))

    def get_current(self, ch: int) -> float:
        return float(self._query(f"IOUT{ch}?").replace('A', ''))

    # Cleanup
    def close(self):
        self.output_off()
        self.ser.close()

    def __del__(self):
        self.close()
