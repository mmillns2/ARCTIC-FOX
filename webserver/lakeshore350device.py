from lakeshore.model_350 import Model350

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
            return float(response)
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 350 "
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
        """
        Heat the still using closed-loop PID temperature control.

        temperature: target temperature in Kelvin
        channel: input channel used for feedback (e.g. 'A')
        output: heater output number (1 or 2)
        power_range: heater range (1=low, 2=medium, 3=high)
        """
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
        """
        Heat the still using open-loop manual power control.

        power_percent: heater power in percent (0–100)
        channel: still sensor (required by OUTMODE but not used for control)
        output: heater output number (1 or 2)
        power_range: heater range (1=low, 2=medium, 3=high)
        """
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
