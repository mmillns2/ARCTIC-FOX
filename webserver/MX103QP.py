import serial
import time

class MX103QP:
    def __init__(self, port, timeout=1.0, name=None):
        self.ser = serial.Serial(
            port=port,
            baudrate=9600,     # ignored for USB, required for RS232
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=timeout
        )

        self.last_voltage = 0
        
        print(f"Connected to MX103QP power supply on {port}")

        # Give the PSU time to settle
        time.sleep(0.2)
        self.all_output_on()
        time.sleep(0.2)

        '''
        for i in range(91):
            volt_out = 9 - i*0.1
            self.set_voltage(1, volt_out)
            time.sleep(1800)
        '''

    def _write(self, cmd: str):
        full = cmd.strip() + "\n"
        self.ser.write(full.encode("ascii"))

    def _query(self, cmd: str) -> str:
        self._write(cmd)
        time.sleep(0.05)
        resp = self.ser.read_until(b"\n")
        return resp.decode("ascii").strip()

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
        #self._write(f"OP{ch} 1")

    def set_current(self, ch: int, amps: float):
        self._write(f"I{ch} {amps}")

    def output_on(self, ch: int):
        self._write(f"OP{ch} 1")

    def output_off(self, ch: int):
        self._write(f"OP{ch} 0")

    def all_output_on(self):
        self.output_on(1)
        self.output_on(2)
        self.output_on(3)
        self.output_on(4)

    def all_output_off(self):
        self.output_off(1)
        self.output_off(2)
        self.output_off(3)
        self.output_off(4)

    def output_state(self, ch: int) -> bool:
        return bool(int(self._query(f"OP{ch}?")))

    # Readout
    def get_voltage(self, ch: int) -> float:
        resp = self._query(f"V{ch}O?")
        if resp is None:    
            return self.last_voltage

        #print(resp)
        cleaned = resp.replace("V", "")
        if not cleaned:
            return self.last_voltage

        try:
            ret = float(cleaned)
            #print(ret)
            self.last_voltage = ret
        except ValueError as e:
            print(f"[MX103QP] ERROR: ", e)
        
        return self.last_voltage

    def read_current(self, ch: int) -> float:
        resp = self._query(f"I{ch}O?")
        return float(resp.replace("A", ""))

    def close(self):
        self.all_output_off()
        self.ser.close()

    def __del__(self):
        self.close()
