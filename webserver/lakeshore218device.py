import serial
import time

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

            # Put device into remote mode without local lockout
            self.write("MODE 1")

            self.input_channels = []
            self.output_channels = []

            self.list_channels()

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
        self.write(cmd)
        return self.ser.readline().decode("ascii").strip()

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
            return float(response)
        except Exception as e:
            print(
                f"Error reading temperature from Lake Shore 218 "
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

