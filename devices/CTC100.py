import re
import serial
import time


class CTC100Device:
    """
    Class to interact with the CTC100 Programmable Temperature Controller.
    Adjusted to align with Lake Shore 372 device methods for duck typing,
    while retaining all original functionality.
    """

    def __init__(self, address, name = None):
        try:
            self.port = address
            self.device = serial.Serial(
                port=address,
                timeout=0
            )
            time.sleep(1)
            self.address = address
            device_status = self.read_status()
            if not device_status:
                raise Exception("No response from CTC100 device")
            self.input_channels = []
            self.output_channels = []
            self.aio_channels = []
            self.list_channels()
            self.name = name
            print(
                f"Connected to CTC100 on {address} with input channels {self.input_channels}, "
                f"output channels {self.output_channels}, and AIO channels {self.aio_channels}"
            )
        except Exception as e:
            print(f"Error initializing CTC100Device on port {address}: {e}")
            raise e  # Re-raise the exception so it can be caught in setup_devices()

    def write(self, command):
        """
        Send a command to the CTC100 over serial and read the response.

        :param command: Command string to send.
        :return: Response from the device.
        """
        self.device.write((command + "\n").encode())  # \n terminates commands
        # Read the response
        t1 = time.time()
        response = b''
        while True:
            response += self.device.read(self.device.in_waiting or 1)
            if response.endswith(b'\r\n'):
                break
            t2 = time.time()
            if (t2 - t1) > 0.2:  # Timeout after 1 second
                break
        # self.device.reset_input_buffer()
        # self.device.reset_output_buffer()
        return response

    def get_variable(self, var):
        """
        Read a parameter from the CTC100.

        :param var: Variable name.
        :return: Value of the variable.
        """
        var = var.replace(" ", "")  # Remove spaces from the variable name
        return self.write("{}?".format(var))

    def set_variable(self, var, val):
        """
        Set a parameter on the CTC100.

        :param var: Variable name.
        :param val: Value to set.
        :return: Response from the device.
        """
        var = var.replace(" ", "")
        val = "({})".format(val)
        return self.write("{} = {}".format(var, val))

    def increment_variable(self, var, val):
        """
        Increment a parameter on the CTC100.

        :param var: Variable name.
        :param val: Value to increment by.
        :return: Response from the device.
        """
        var = var.replace(" ", "")
        val = "({})".format(val)
        return self.write("{} += {}".format(var, val))

    def setAlarm(self, channel, Tmin, Tmax):
        """
        Enable and configure an alarm on a channel within specified temperature limits.

        :param channel: Channel number or name.
        :param Tmin: Minimum temperature limit.
        :param Tmax: Maximum temperature limit.
        """
        if not isinstance(channel, str):
            channel = f"In{channel}"

        self.set_variable(f"{channel}.Alarm.Sound", "4 beeps")
        self.set_variable(f"{channel}.Alarm.Min", str(Tmin))
        self.set_variable(f"{channel}.Alarm.Max", str(Tmax))
        response = self.set_variable(f"{channel}.Alarm.Mode", "Level")
        return response

    def disableAlarm(self, channel):
        """
        Disable the alarm on a channel.

        :param channel: Channel number or name.
        """
        if not isinstance(channel, str):
            channel = f"In{channel}"

        response = self.set_variable(f"{channel}.Alarm.Mode", "Off")
        return response

    def get_temperature(self, channel):
        """
        Read the temperature from an input or AIO channel.
        
        :param channel: Channel number or name.
        :return: Temperature value.
        """
        try:
            if not isinstance(channel, str):
                if channel in self.input_channels:
                    channel = channel
                elif f"{channel}" in self.aio_channels:
                    channel = f"{channel}"
                else:
                    raise ValueError(f"Channel {channel} not found.")
            temp = self.read(channel)
            return temp
        except Exception as e:
            print(
                f"Error reading temperature from CTC100 (Channel {channel}): {e}")
            return None

    def read(self, channel):
        """
        Read the value from an input or output channel.

        :param channel: Channel name (e.g., 'In1').
        :return: The value read from the channel.
        """
        response = self.get_variable(f"{channel}.Value")
        # Extract the numerical value from the response
        match = re.search(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?",
                          response.decode("utf-8"))
        if match is not None:
            return float(match.group())
        else:
            raise RuntimeError(f"Unable to read from channel {channel}")

    def read_all_channels(self):
        """
        Read values from all input and AIO channels.

        :return: Dictionary with channel names as keys and readings as values.
        """
        readings = {}
        for channel in self.input_channels + self.aio_channels:
            temp = self.get_temperature(channel)
            readings[channel] = temp
        return readings

    def enable_heater(self):
        """
        Enable all heaters (outputs).
        """
        self.write("OutputEnable On")

    def disable_heater(self):
        """
        Disable all heaters (outputs).
        """
        self.write("OutputEnable Off")

    def set_heater_output(self, channel, value=0.0):
        """
        Set the heater output percentage in Manual mode.

        :param heater_number: Heater (output) channel number (1 or 2).
        :param heat_percent: Output percentage to set (0-100%).
        :return: True if successful, False otherwise.
        """
        try:
            self.write(f'{channel}.Value {value}')
            return True
        except Exception as e:
            print(f"Error setting heater output on CTC100: {e}")
            return False

    def set_control_mode(self, channel, mode):
        """
        Set the control mode of an output channel.

        :param channel: Output channel number (1 or 2).
        :param mode: Control mode ('Off', 'Manual', 'PID').
        :return: Response from the device.
        """
        if mode not in ['Off', 'Manual', 'PID']:
            raise ValueError(
                "Invalid control mode. Must be 'Off', 'Manual', or 'PID'.")
        return self.set_variable(f"{channel}.Heater.Mode", mode)
    
    def set_PID_mode(self, channel, mode):
        """
        Set the control mode of an output channel.

        :param channel: Output channel number (1 or 2).
        :param mode: Control mode ('Off', 'Manual', 'PID').
        :return: Response from the device.
        """
        if mode not in ['Off', 'On', 'Follow']:
            raise ValueError(
                "Invalid control mode. Must be 'Off', 'On', or 'Follow'.")
        return self.set_variable(f"{channel}.PID.Mode", mode)

    def enable_PID(self, channel):
        """
        Enable PID control on an output channel.

        :param channel: Output channel number (1 or 2).
        """
        self.set_PID_mode(channel, 'On')

    def disable_PID(self, channel):
        """
        Disable PID control on an output channel.

        :param channel: Output channel number (1 or 2).
        """
        self.set_PID_mode(channel, 'Off')

    def write_setpoint(self, channel, setpoint):
        """
        Set the setpoint value of an output channel.

        :param channel: Output channel number (1 or 2).
        :param setpoint: Setpoint value in Kelvin.
        :return: Response from the device.
        """
        return self.set_variable(f"{channel}.PID.Setpoint", setpoint)

    def read_setpoint(self, channel):
        """
        Read the setpoint value of an output channel.

        :param channel: Output channel number (1 or 2).
        :return: Setpoint value.
        """
        response = self.get_variable(f"Out{channel}.PID.Setpoint")
        match = re.search(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?",
                          response.decode("utf-8"))
        if match is not None:
            return float(match.group())
        else:
            raise RuntimeError(f"Unable to read setpoint from Out{channel}")

    def tune_PID(self, channel, StepY, Lag):
        """
        Begin PID auto-tuning on an output channel.

        :param channel: Output channel number (1 or 2).
        :param StepY: Heater power to apply during tuning (in Watts).
        :param Lag: Duration of the tuning step (in seconds).
        """
        self.set_variable(f"{channel}.Tune.StepY", StepY)
        self.set_variable(f"{channel}.Tune.Lag", Lag)

        # self.enable_heater()
        self.set_variable(f"{channel}.Tune.Type", "Auto")
        self.set_variable(f"{channel}.Tune.Mode", "Auto")  # Begin tuning

        # Sleep during the tuning process
        time.sleep(Lag + 3*Lag)  # Adding extra time for safety

        # Check if tuning was successful
        response = self.get_variable(f"{channel}.PID.Mode").decode()
        if "On" in response:
            print("PID tuning was successful! The parameters have been updated.")
            self.disable_PID(channel)
        else:
            print("PID tuning failed! Try higher values for StepY or Lag.")

    def set_PID_parameters(self, channel, P, I, D):
        """
        Set the PID parameters (P, I, D values) on an output channel.

        :param channel: Output channel number (1 or 2).
        :param P: Proportional gain.
        :param I: Integral gain.
        :param D: Derivative gain.
        """
        self.set_variable(f"Out{channel}.PID.P", P)
        self.set_variable(f"Out{channel}.PID.I", I)
        self.set_variable(f"Out{channel}.PID.D", D)
        print(f"PID parameters for Out{channel} set to P={P}, I={I}, D={D}")

    def read_PID_parameters(self, channel):
        """
        Read the PID parameters (P, I, D values) from an output channel.

        :param channel: Output channel number (1 or 2).
        :return: Dictionary containing 'P', 'I', 'D' parameters.
        """
        params = {}
        for param in ['P', 'I', 'D']:
            response = self.get_variable(f"Out{channel}.PID.{param}")
            match = re.search(
                r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", response.decode("utf-8"))
            if match is not None:
                params[param] = float(match.group())
            else:
                raise RuntimeError(
                    f"Unable to read PID {param} from Out{channel}")
        return params

    def read_status(self):
        """
        Read the device's status.

        :return: Device status information.
        """
        response = self.write('Status')
        return response.decode().strip()

    def read_alarms(self):
        """
        Read active alarms on the device.

        :return: Alarm information.
        """
        response = self.write('Alarm')
        return response.decode().strip()

    def list_channels(self):
        try:
            # Get all channel names using 'getOutput.names' command
            response = self.get_variable('getOutput.names')
            decoded_response = response.decode().strip()
            decoded_response = decoded_response.replace('getOutput.names', '')
            channel_names = [name.strip()
                            for name in decoded_response.split(',') if name.strip()]

            
            for i,name in enumerate(channel_names):
                if i <4:
                    self.input_channels.append(name)
                elif i>3 and i<6:
                    self.output_channels.append(name)
                else:
                    self.aio_channels.append(name)
                
        except Exception as e:
            print(f"Error listing channels on CTC100: {e}")
            raise e  # Re-raise the exception to indicate failure
            # If any error occurs, default to predefined channels
            self.input_channels = ['In1', 'In2']
            self.output_channels = ['Out1', 'Out2']
            self.aio_channels = ['AIO1', 'AIO2', 'AIO3', 'AIO4']

    def get_input_channels(self):
        """
        Get the list of input channels.

        :return: List of input channel names.
        """
        return self.input_channels

    def get_output_channels(self):
        """
        Get the list of output channels.

        :return: List of output channel names.
        """
        return self.output_channels

    def get_aio_channels(self):
        """
        Get the list of output channels.

        :return: List of output channel names.
        """
        return self.aio_channels
    def link_heater_to_input(self, output_channel, input_channel):
        """
        Link a heater (output channel) with a thermometer (input channel) for PID control.

        :param output_channel: Output channel number (1 or 2).
        :param input_channel: Input channel number or name.
        :return: None.
        """
        # Ensure input channel format
        if not isinstance(input_channel, str):
            input_channel_name = f"{input_channel}"
        else:
            input_channel_name = input_channel

        # Construct the command without an '='
        command = f"{output_channel}.PID.Input {input_channel_name}"
        response = self.send_command(command)

        # Enable PID control
        self.enable_PID(output_channel)
        
        print(response)
        print(
            f"Linked {output_channel} to {input_channel_name} for PID control.")
        
    def get_aio_iotype(self, channel):
        """
        Get the IOType of an AIO channel.

        :param channel: AIO channel number or name (e.g., 'AIO1' or 1).
        :return: IOType of the channel ('Input', 'Set out', or 'Meas out').
        """
        if not isinstance(channel, str):
            channel = f"{channel}"
        response = self.get_variable(f"{channel}.IOType")
        # Extract the IOType from the response
        response_str = response.decode().strip()
        match = re.search(rf"{channel}.IOType=(.*)", response_str)
        if match:
            iotype = match.group(1).strip()
            return iotype
        else:
            # If response doesn't contain '=', try parsing the raw response
            return response_str

    def set_aio_iotype(self, channel, iotype):
        """
        Set the IOType of an AIO channel.

        :param channel: AIO channel number or name (e.g., 'AIO1' or 1).
        :param iotype: IOType to set ('Input', 'Set out', or 'Meas out').
        :return: Response from the device.
        """
        valid_iotypes = ['Input', 'Set Out', 'Meas out']
        if iotype not in valid_iotypes:
            raise ValueError(
                f"Invalid IOType. Must be one of {valid_iotypes}.")
        if not isinstance(channel, str):
            channel = f"{channel}"
        # Set the IOType using the appropriate format
        response = self.set_variable(f"{channel}.IOType", f'"{iotype}"')
        return response

    def get_aio_voltage(self, channel):
        """
        Get the voltage of an AIO channel configured as output ('Set out').

        :param channel: AIO channel number or name (e.g., 'AIO1' or 1).
        :return: Voltage value in volts.
        """
        if not isinstance(channel, str):
            channel = f"{channel}"
        # Ensure the channel is configured as 'Set out'
        iotype = self.get_aio_iotype(channel)
        if iotype != 'Set out':
            raise RuntimeError(
                f"{channel} is not configured as 'Set out'. Current IOType: {iotype}")
        response = self.get_variable(f"{channel}.Value")
        # Extract the voltage value from the response
        match = re.search(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?",
                          response.decode("utf-8"))
        if match:
            voltage = float(match.group())
            return voltage
        else:
            raise RuntimeError(f"Unable to read voltage from {channel}")

    def set_aio_voltage(self, channel, voltage):
        """
        Set the voltage of an AIO channel configured as output ('Set out').

        :param channel: AIO channel number or name (e.g., 'AIO1' or 1).
        :param voltage: Voltage value to set (between -10 and +10 volts).
        :return: Response from the device.
        """
        if not (-10.0 <= voltage <= 10.0):
            raise ValueError("Voltage must be between -10 and +10 volts.")
        if not isinstance(channel, str):
            channel = f"{channel}"
        # Ensure the channel is configured as 'Set out'
        iotype = self.get_aio_iotype(channel)
        if iotype != 'Set out':
            raise RuntimeError(
                f"{channel} is not configured as 'Set out'. Current IOType: {iotype}")
        # Set the voltage using the appropriate command
        response = self.set_variable(f"{channel}.Value", voltage)
        return response

    def send_command(self, command):
        """
        Send a custom command to the device and return the response.

        :param command: Custom command string.
        :return: Response from the device.
        """
        response = self.write(command)
        return response.decode().strip()

    def __del__(self):
        """
        Destructor to ensure the serial port is closed when the object is deleted.
        """
        try:
            self.device.close()
        except Exception:
            pass

