from lakeshore import Model336

class LakeShore336Device:
    def __init__(self, port, name = None):
        try:
            if Model336 is None:
                raise ImportError("Lake Shore Model336 driver not available.")
                
            self.device = Model336(com_port=port)

            self.port = port
            self.address = port  # Added to store the address
            self.name = name
            
            self.input_channels = []
            self.output_channels = []

            self.list_channels()

            print(
                f"Connected to Lake Shore 336 on {port} with channels {self.input_channels} and output channels {self.output_channels}")
        except Exception as e:
            raise e

    def get_input_channels(self):
        '''
        Returns input channels.
        '''
        return self.input_channels

    def get_output_channels(self):
        '''
        There are no output channels for this device.
        '''
        return [] 

    def get_temperature(self, channel):
        '''
        Read temperature in Kelvin from input channel A–D.
        Uses package API.
        '''
        try:
            temp = self.device.get_kelvin_reading(channel)
            return temp
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 336 (Channel {channel}): {e}"
            )
            return None


    def get_voltage(self, channel):
        '''
        Read voltage in Ohms from input channel A–D.
        Uses package API.
        '''
        try:
            readings = self.device.get_all_sensor_reading()
            temp = -10
            match channel:
                case 'A':
                    temp = readings[0] 
                case 'B':
                    temp = readings[1] 
                case 'C':
                    temp = readings[2] 
                case 'D':
                    temp = readings[3] 

            #print(f'336: {channel} = {temp} V')
            return temp
        except Exception as e:
            print(
                f"Error reading resistance from Lake Shore 336 (Channel {channel}): {e}"
            )
            return None


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
        List available input channels on the Lake Shore 224.

        Channel names are 'A', 'B', 'C', 'D' 
        '''
        self.input_channels = ['A', 'B', 'C', 'D'] 
