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

    def list_channels(self):
        '''
        List available input channels on the Lake Shore 350.

        Channel names are 'A', 'B', 'C', 'D', 'D1' - 'D5'.
        '''
        self.input_channels = ['A', 'B', 'C', 'D'] + [f'D{i}' for i in range(1, 5)]
