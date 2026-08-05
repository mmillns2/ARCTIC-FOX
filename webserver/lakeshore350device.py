from lakeshore.model_350 import Model350

from calibration_data import CALIBRATION_TEMPERATURES, CALIBRATION_RESISTANCES

import numpy as np
import time
import os

class LakeShore350Device:
    def __init__(self, port, name=None):
        try:
            if Model350 is None:
                raise ImportError("Lake Shore Model 350 driver not available.")

            self.device = Model350(com_port=port)

            self.port = port
            self.address = port     # Added to store the address
            self.name = name

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
            print(f"350 assigned curve: {self.get_assigned_curve(1)}")  # should print 21

            hdr, r, t = self.get_curve(21)
            print(f"350 header: {hdr}")
            print(f"350 len: {len(r)}")
            '''

            print(f"Connected to Lake Shore 350 on {port} with input channels {self.input_channels} and output channels {self.output_channels}")

        except Exception as e:
            raise e

    def get_input_channels(self):
        '''
        Returns input channels.
        '''
        return self.input_channels

    def get_output_channels(self):
        '''
        There are output channels for this device but we won't use them for now.
        '''
        return []

    def get_temperature(self, channel):
        '''
        Read temperature in Kelvin from input channel A–D(1-5).
        Uses KRDG? query.
        '''
        try:
            response = self.device.query(f"KRDG? {channel}")
            ret = float(response)
            #print(f'350: {channel} = {response}')
            return ret
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 350 "
                f"(Channel {channel}): {e}"
            )
            return None

    def get_resistance(self, channel):
        '''
        Read resistance in Omhs from input channel A–D1.
        Uses SRDG? query which returns resistance for cernox channels.
        '''
        try:
            response = self.device.query(f"SRDG? {channel}")
            ret = float(response)
            #print(f'350: {channel} = {response} R')
            return ret
        except Exception as e:
            print(
                f"Error reading resistance from Lake Shore 350 "
                f"(Channel {channel}): {e}"
            )
            return None

    def get_voltage(self, channel):
        '''
        Read voltage in volts from input channel D1-D5.
        Uses SRDG? query which returns voltage for diode channels.
        '''
        try:
            response = self.device.query(f"SRDG? {channel}")
            ret = float(response)
            #print(f'350: {channel} = {response} V')
            return ret
        except Exception as e:
            print(
                f"Error reading voltage from Lake Shore 350 "
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

    def set_still_voltage(self, percent):
        '''
        Apply a voltage to the still using the Lakeshore 350.
        percent is the proportion of total still power that can be applied.
        '''
        pass

    def heat_still_pid(self, temperature, channel="A", output=1, power_range=1):
        '''
        Heat the still using closed-loop PID temperature control.

        temperature: target temperature in Kelvin
        channel: input channel used for feedback (e.g. 'A')
        output: heater output number (1 or 2)
        power_range: heater range (1=low, 2=medium, 3=high)
        '''
        try:
            # Select closed-loop PID mode
            self.device.write(f"OUTMODE {output},1,{sensor},0")

            # Enable heater output
            self.device.write(f"RANGE {output},{power_range}")

            # Set temperature setpoint
            self.device.write(f"SETP {output},{temperature}")

        except Exception as e:
            print(f"Error enabling PID still heating: {e}")

    def heat_still_manual(self, power_percent, channel="A", output=1, power_range=1):
        '''
        Heat the still using open-loop manual power control.

        power_percent: heater power in percent (0–100)
        channel: still sensor (required by OUTMODE but not used for control)
        output: heater output number (1 or 2)
        power_range: heater range (1=low, 2=medium, 3=high)
        '''
        try:
            # Select manual output mode
            self.device.write(f"OUTMODE {output},3,{sensor},0")

            # Enable heater output
            self.device.write(f"RANGE {output},{power_range}")

            # Set manual heater power
            self.device.write(f"MOUT {output},{power_percent}")

        except Exception as e:
            print(f"Error enabling manual still heating: {e}")

    def list_channels(self):
        '''
        List available input channels on the Lake Shore 350.

        Channel names are 'A', 'B', 'C', 'D', 'D1' - 'D5'.
        '''
        self.input_channels = ['A', 'B', 'C', 'D'] + [f'D{i}' for i in range(1, 5)]


    def assign_curve_to_channel(self, channel, curve_number):
        '''
        Assign a curve (21–28) to an input channel (A-D,D1-D5).
        '''
        self.device.write(f"INCRV {channel},{curve_number}")
        time.sleep(0.2)

        response = self.device.query(f"INCRV? {channel}")
        print(f"Assigned curve response: {response}")


    def get_assigned_curve(self, channel):
        '''
        Query which curve is assigned to a channel.
        '''
        response = self.device.query(f"INCRV? {channel}")
        print(response)

        if not response:
            raise RuntimeError("No response from INCRV?")

        return int(response)


    def get_curve(self, curve_number):
        '''
        Retrieve curve data from the Lake Shore 350.

        Returns:
            header: dict
            resistances: list
            temperatures: list
        '''

        # Get header
        hdr = self.device.query(f"CRVHDR? {curve_number}")
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
            response = self.device.query(f"CRVPT? {curve_number},{i}")

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
            print(f"Lakeshore350: Downsampled curve from {n} -> {max_points} points")

        if temp_limit is None:
            temp_limit = float(np.max(temps))

        name = name[:15]
        serial_number = serial_number[:10]

        # Delete existing curve
        self.device.write(f"CRVDEL {curve_number}")
        time.sleep(0.1)

        # Configure header
        self.device.write(
            f"CRVHDR {curve_number},{name},{serial_number},{format_code},{temp_limit:.3f},{coefficient}"
        )
        time.sleep(1)
        print(self.device.query(f"CRVHDR? {curve_number}"))
        time.sleep(0.1)

        # Upload points
        for i, (r, t) in enumerate(zip(res, temps), start=1):
            self.device.write(f"CRVPT {curve_number},{i},{r:.6f},{t:.6f}")
            time.sleep(0.02)

        time.sleep(0.5)         # let device process

        print(f"Lakeshore350: Curve {curve_number} uploaded with {len(res)} points.")

