from lakeshore.model_224 import Model224, Model224Enums

SensorType = Model224Enums.InputSensorType


class LakeShore224Device:
    """
    Class to interact with the Lake Shore 224 Temperature Monitor using the official driver.
    """

    def __init__(self, port, name=None):
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

    def _get_sensor_units(self, channel, expected_types, label):
        '''
        Read raw sensor-units value from input A, B, C1–C5 or D1–D5,
        after confirming the input's sensor type matches what we expect.
        '''
        try:
            cfg = self.device.get_input_configuration(channel)
            if cfg.sensor_type not in expected_types:
                print(
                    f"Lake Shore 224 (Channel {channel}) is configured as "
                    f"{cfg.sensor_type.name}, not a {label} sensor"
                )
                return None
            res = self.device.get_sensor_reading(channel)
            return float(res)
        except Exception as e:
            print(
                f"Error reading {label} from Lake Shore 224 (Channel {channel}): {e}"
            )
            return None

    def get_voltage(self, channel):
        '''
        Read voltage in Volts from a diode input (A, B, C1–C5, D1–D5).
        Uses package API.
        '''
        return self._get_sensor_units(channel, (SensorType.DIODE,), "voltage")

    def get_resistance(self, channel):
        '''
        Read resistance in Ohms from an RTD input (A, B, C1–C5, D1–D5).
        Uses package API.
        '''
        return self._get_sensor_units(
            channel,
            (SensorType.PLATINUM_RTD, SensorType.NTC_RTD),
            "resistance",
        )

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
