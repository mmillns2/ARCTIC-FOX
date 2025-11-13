from lakeshore.model_224 import Model224


class LakeShore224Device:
    """
    Class to interact with the Lake Shore 224 Temperature Monitor using the official driver.
    """

    def __init__(self, port, name = None):
        try:
            if Model224 is not None:
                self.device = Model224(com_port=port)
            else:
                raise ImportError("Lake Shore Model224 driver not available.")
            self.port = port
            self.address = port  # Added to store the address
            self.input_channels = []
            self.list_channels()
            self.name = name
            print(
                f"Connected to Lake Shore 224 on {port} with channels {self.input_channels}")
        except Exception as e:
            raise e

    def get_input_channels(self):
        return self.input_channels

    def get_output_channels(self):
        return []  # Lake Shore 224 has no output channels

    def get_temperature(self, channel):
        try:
            temp = self.device.get_kelvin_reading(channel)
            return temp
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 224 (Channel {channel}): {e}"
            )
            return None

    def read_all_channels(self):
        readings = {}
        for channel in self.input_channels:
            temp = self.get_temperature(channel)
            readings[channel] = temp
        return readings

    def list_channels(self):
        """
        List available input channels on the Lake Shore 224.

        Channel names are 'A', 'B', 'C1' - 'C5', 'D1' - 'D5'.
        """
        self.input_channels = ['A', 'B'] + \
            [f'C{i}' for i in range(1, 6)] + [f'D{i}' for i in range(1, 6)]
