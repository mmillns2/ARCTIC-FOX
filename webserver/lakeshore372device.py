from lakeshore.model_372 import Model372, Model372HeaterOutputSettings


class LakeShore372Device:
    """
    Class to interact with the Lake Shore 372 Temperature Controller using the official driver.
    """

    def __init__(self, port, name = None):
        try:
            if Model372 is None:
                raise ImportError("Lake Shore Model 372 driver not available.")
            
            self.device = Model372(baud_rate=57600, com_port=port)

            self.port = port
            self.address = port  # Added to store the address
            self.name = name

            self.input_channels = []
            self.output_channels = []

            self.list_channels()
            print(
                f"Connected to Lake Shore 372 on {port} with input channels {self.input_channels} and output channels {self.output_channels}")

        except Exception as e:
            raise e

    def get_input_channels(self):
        return self.input_channels

    def get_output_channels(self):
        return self.output_channels

    def get_temperature(self, channel):
        '''
        Read temperature in Kelvin from input channel 1–16 or A.
        Uses package API.
        '''
        try:
            temp = self.device.get_kelvin_reading(channel)
            ret = float(temp)
            #print(f'372: {channel} = {temp}')
            return ret
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 372 (Channel {channel}): {e}"
            )
            return None

    def get_resistance(self, channel):
        '''
        Read resistance in Ohms from input channel 1–16 or A.
        Uses package API.
        '''
        try:
            res = self.device.get_resistance_reading(channel)
            ret = float(res)
            #print(f'372: {channel} = {res}')
            return ret
        except Exception as e:
            print(
                f"Error reading resistance from Lake Shore 372 (Channel {channel}): {e}"
            )
            return None

    def get_voltage(self, ch: int) -> float:
        '''
        Currently, only works for Still.
        Config loader api wrapper.
        Returns voltage applied to Still as a percentage.
        '''
        return self.get_still_output()

    def set_voltage(self, ch: int, volts: float):
        '''
        Currently, only works for Still.
        Config loader api wrapper.
        Sets voltage to Still as a percentage.
        '''
        self.set_still_output(volts)
        
    def read_all_channels(self):
        '''
        Read out temperature of all channels.
        '''
        readings = {}
        for channel in self.input_channels:
            temp = self.get_temperature(channel)
            readings[channel] = temp
        return readings

    def list_channels(self):
        '''
        List available input channels on the Lake Shore 218.
        Channels are 1–16 and A.
        Output channels are '1' (Warm-up heater), '2' (Analog output).
        '''
        self.input_channels = [str(i) for i in range(1, 17)] + ['A']
        self.output_channels = ['sample_heater', 'still_heater']

    def get_still_output(self):
        '''
        Read the still heater output voltage as a percentage (0–100%).
        '''
        try:
            val = self.device.get_still_output()
            return float(val)
        except Exception as e:
            print(f"Error reading still heater output on Lake Shore 372: {e}")
            return None

    def set_still_output(self, voltage_percentage):
        '''
        Set the still heater output voltage as a percentage (0–100%).
        '''
        try:
            voltage_percentage = float(voltage_percentage)
            if not 0.0 <= voltage_percentage <= 100.0:
                raise ValueError(f"Voltage percentage must be between 0 and 100, got {voltage_percentage}")
            self.device.set_still_output(voltage_percentage)
            return True
        except Exception as e:
            print(f"Error setting still heater output on Lake Shore 372: {e}")
            return False



"""
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
        '''
        List available input and output channels on the Lake Shore 372.

        Input channels are '1' - '16', or 'A'.
        Output channels are '1' (Warm-up heater), '2' (Analog output).
        '''
        self.input_channels = [str(i) for i in range(1, 17)] + ['A']
        self.output_channels = ['sample_heater', 'still_heater']

    def sample_heater_output_percentage(self):
        return float(self.device.query('HTR?'))
    
    def still_heater_output_query(self):
        return self.device.get_still_output()
    
    def get_output(self, channel):
        if channel == 'sample_heater':
            return self.sample_heater_output_percentage()
        elif channel == 'still_heater':
            return self.still_heater_output_query()

    def set_still_voltage(self, voltage_percentage):
        self.device.set_still_output(voltage_percentage)

    def set_MC_setpoint(self, setpoint):
        self.device.set_setpoint_kelvin(0, setpoint)

    def MC_heater_turn_off(self):
        self.device.set_heater_output_range(0, self.device.SampleHeaterOutputRange(0))
"""
