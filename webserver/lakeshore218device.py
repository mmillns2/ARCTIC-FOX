import serial
import time
import numpy as np

from calibration_data import CALIBRATION_TEMPERATURES, CALIBRATION_RESISTANCES

class LakeShore218Device:
    def __init__(self, port, name=None, timeout=1.0):
        try:
            self.port = port
            self.address = port     # Added to store the address
            self.name = name

            self.ser = serial.Serial(
                port=port,
                baudrate=9600,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_ODD,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
            )

            time.sleep(0.1)
            # Put device into remote mode without local lockout
            self.write("MODE 1")
            #time.sleep(0.1)
            #print(f"218 mode: {self.query("MODE?")}")

            self.input_channels = []
            self.output_channels = []

            self.list_channels()

            '''
            self.set_curve(
                curve_number=21,
                temperatures=CALIBRATION_TEMPERATURES,
                resistances=CALIBRATION_RESISTANCES,
                name="CALCC9",
                serial_number="123456",        
            )
            time.sleep(1)
            self.assign_curve_to_channel(1, 21)
            time.sleep(1)
            print(self.get_assigned_curve(1))  # should print 21

            hdr, r, t = self.get_curve(21)
            print(hdr)
            print(len(r))
            '''

            print(f"Connected to Lake Shore 218 on {port} with input channels {self.input_channels} and output channels {self.output_channels}")

        except Exception as e:
            raise e

    def write(self, cmd):
        '''
        Writes a command to Lake shore 218.
        Does not return anything.
        '''
        self.ser.write((cmd + "\r\n").encode("ascii"))

    def query(self, cmd):
        '''
        Writes command to Lake shore 218 and returns a response string.
        '''
        self.ser.reset_input_buffer()
        self.write(cmd)
        time.sleep(0.1)
        resp = self.ser.readline()
        #print(f"RAW: {resp}")
        return resp.decode("ascii").strip()

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def get_input_channels(self):
        '''
        Returns input channels.
        '''
        return self.input_channels

    def get_output_channels(self):
        '''
        Model 218 has no analog control outputs.
        '''
        return []

    def get_temperature(self, channel):
        '''
        Read temperature in Kelvin from input channel 1–8.
        Uses KRDG? query.
        '''
        try:
            response = self.query(f"KRDG? {channel}")
            #print(f'218: {channel} = {response}')
            ret = float(response)
            return ret
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 218 "
                f"(Channel {channel}): {e}"
            )
            return None

    
    def get_voltage(self, channel):
        '''
        Read voltage in volts from input channel 1-8.
        Uses SRDG? query which returns voltage for diode channels.
        '''
        try:
            response = self.query(f"SRDG? {channel}")
            ret = float(response)
            #print(f'218: {channel} = {response} V')
            return ret
        except Exception as e:
            print(
                f"Error reading voltage from Lake Shore 218 "
                f"(Channel {channel}): {e}"
            )
            return None


    def read_all_channels(self):
        '''
        Read out temperature of all channels.
        '''
        readings = {}
        for channel in self.input_channels:
            readings[channel] = self.get_temperature(channel)
        return readings


    def list_channels(self):
        '''
        List available input channels on the Lake Shore 218.

        Channels are 1–8.
        '''
        self.input_channels = list(range(1, 9))


    def assign_curve_to_channel(self, channel, curve_number):
        '''
        Assign a curve (21–28) to an input channel (1–8).
        '''
        self.write(f"INCRV {channel},{curve_number}")


    def get_assigned_curve(self, channel):
        '''
        Query which curve is assigned to a channel.
        '''
        response = self.query(f"INCRV? {channel}")
        print(response)

        if not response:
            raise RuntimeError("No response from INCRV?")

        return int(response)


    def get_curve(self, curve_number):
        '''
        Retrieve curve data from the Lake Shore 218.

        Returns:
            header: dict
            resistances: list
            temperatures: list
        '''

        # Get header
        hdr = self.query(f"CRVHDR? {curve_number}")
        name, sn, fmt, limit, coeff = hdr.split(",")

        header = {
            "name": name.strip(),
            "serial": sn.strip(),
            "format": int(fmt),
            "limit": float(limit),
            "coefficient": int(coeff),
        }

        resistances = []
        temperatures = []

        # Read points
        for i in range(1, 201):
            response = self.query(f"CRVPT? {curve_number},{i}")

            if not response:
                break

            try:
                r_str, t_str = response.split(",")
                r = float(r_str)
                t = float(t_str)

                # Stop if empty point (device returns zeros sometimes)
                if r == 0 and t == 0:
                    break

                resistances.append(r)
                temperatures.append(t)

            except Exception:
                break

        return header, np.array(resistances), np.array(temperatures)


    def set_curve(
        self,
        curve_number,
        temperatures,
        resistances,
        name="USERCURVE",
        serial_number="00000001",
        format_code=3,
        temp_limit=None,
        coefficient=1
    ):

        temps = np.asarray(temperatures)
        res = np.asarray(resistances)

        if temps.shape != res.shape:
            raise ValueError("Temperature and resistance arrays must have same shape")

        # Sort by resistance (required)
        sort_idx = np.argsort(res)
        res = res[sort_idx]
        temps = temps[sort_idx]

        # Downsample if needed
        max_points = 200
        n = len(res)

        if n > max_points:
            # Evenly spaced indices INCLUDING endpoints
            indices = np.linspace(0, n - 1, max_points, dtype=int)
            res = res[indices]
            temps = temps[indices]
            print(f"Lakeshore218: Downsampled curve from {n} -> {max_points} points")

        if temp_limit is None:
            temp_limit = float(np.max(temps))

        name = name[:15]
        serial_number = serial_number[:10]

        # Delete existing curve
        self.write(f"CRVDEL {curve_number}")
        time.sleep(0.1)

        # Configure header
        self.write(
            f"CRVHDR {curve_number},{name},{serial_number},{format_code},{temp_limit:.3f},{coefficient}"
        )
        time.sleep(0.1)

        # Upload points
        for i, (r, t) in enumerate(zip(res, temps), start=1):
            self.write(f"CRVPT {curve_number},{i},{r:.6f},{t:.6f}")
            time.sleep(0.02)

        self.ser.flush()        # ensure all writes sent
        time.sleep(0.5)         # let device process

        print(f"Lakeshore218: Curve {curve_number} uploaded with {len(res)} points.")

