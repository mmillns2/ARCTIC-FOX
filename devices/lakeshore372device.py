from lakeshore.model_372 import Model372, Model372HeaterOutputSettings


class LakeShore372Device:
    """
    Class to interact with the Lake Shore 372 Temperature Controller using the official driver.
    """

    def __init__(self, port, name = None):
        try:
            if Model372 is not None:
                self.device = Model372(com_port=port, baud_rate=57600)
            else:
                raise ImportError("Lake Shore Model372 driver not available.")
            self.port = port
            self.address = port  # Added to store the address
            self.input_channels = []
            self.output_channels = []
            self.list_channels()
            self.name = name
            print(
                f"Connected to Lake Shore 372 on {port} with input channels {self.input_channels} and output channels {self.output_channels}")
        except Exception as e:
            raise e

    def get_input_channels(self):
        return self.input_channels

    def get_output_channels(self):
        return self.output_channels

    def get_temperature(self, channel):
        try:
            if channel == 'A':
                temp = self.device.get_all_input_readings(channel)['kelvin']
            else:
                temp = self.device.get_all_input_readings(int(channel))['kelvin']
            return temp
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 372 (Channel {channel}): {e}"
            )
            return None

    def read_all_channels(self):
        readings = {}
        for channel in self.input_channels:
            temp = self.get_temperature(channel)
            readings[channel] = temp
        return readings

    # def set_heater_output(self, heater_number=1, heat_percent=0.0):
    #     try:
    #         # Setting heater output percentage according to the official driver methods
    #         heater_number = int(heater_number)
    #         if heater_number == 1:
    #             self.device.set_heater_output_percentage(heat_percent)
    #         elif heater_number == 2:
    #             self.device.set_analog_heater_output(heat_percent)
    #         return True
    #     except Exception as e:
    #         print(f"Error setting heater output on Lake Shore 372: {e}")
            # return False
    def get_sensor(self, channel):
        try:
            if channel == 'A':
                temp = self.device.get_all_input_readings(channel)['resistance']
            else:
                temp = self.device.get_all_input_readings(int(channel))['resistance']
            return temp
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 372 (Channel {channel}): {e}"
            )
            return None

    def list_channels(self):
        """
        List available input and output channels on the Lake Shore 372.

        Input channels are '1' - '16', or 'A'.
        Output channels are '1' (Warm-up heater), '2' (Analog output).
        """
        self.input_channels = [str(i) for i in range(1, 17)] + ['A']
        self.output_channels = ['sample_heater', 'still_heater']

    def sample_heater_output_percentage(self):
        return float(self.device.query('HTR?'))
    
    def still_heater_output_query(self):
        return self.device.get_still_output()
    
    def get_output(self, channel):
        if channel is 'sample_heater':
            return self.sample_heater_output_percentage()
        elif channel is 'still_heater':
            return self.still_heater_output_query()

    def set_still_voltage(self, voltage_percentage):
        self.device.set_still_output(voltage_percentage)

    def set_MC_setpoint(self, setpoint):
        self.device.set_setpoint_kelvin(0, setpoint)

    def MC_heater_turn_off(self):
        self.device.set_heater_output_range(0, self.device.SampleHeaterOutputRange(0))
