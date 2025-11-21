import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit
)
from PyQt5.QtCore import Qt
from cooldown_loop_dilution_v2 import switch_on, switch_off, heater_on, heater_off
from CTC100 import CTC100Device
from lakeshore224device import LakeShore224Device
from lakeshore372device import LakeShore372Device
import serial

 # Active Regulation & Control of Thermal Interfaces for Cryogenic Fridge Operation eXperiments (ARCTIC FOX)

def connect_devices():  # Connects to devices
    devices = serial.tools.list_ports.comports()

    ctc100A = None
    ctc100B = None
    model224 = None
    model372 = None

    for device in devices:
        if 'FT230X' in device.description:
            if 'DK0CDLQP' in device.serial_number:
                ctc100B = CTC100Device(address=device.device, name='CTC100B')
            elif 'DK0CDKFB' in device.serial_number:
                ctc100A = CTC100Device(address=device.device, name='CTC100A')

        elif '224' in device.description:
            model224 = LakeShore224Device(port=device.device, name='LakeshoreModel224')

        elif '372' in device.description:
            model372 = LakeShore372Device(port=device.device, name='LakeshoreModel372')

    connected = {
        "CTC100A": ctc100A,
        "CTC100B": ctc100B,
        "LakeshoreModel372": model372,
        "LakeshoreModel224": model224,
    }

    return {k: v for k, v in connected.items() if v is not None}


class SwitchWidget(QWidget):  # Creates inputs for heat switches, these have voltage inputs
    def __init__(self, device, channel):
        super().__init__()
        self.device = device
        self.channel = channel
        self.state = False  # OFF by default

        layout = QVBoxLayout()
        self.setLayout(layout)



        # Label for channel
        label = QLabel(f"SWITCH ({channel})")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # Voltage input row
        row = QHBoxLayout()

        self.voltage_input = QLineEdit()
        self.voltage_input.setPlaceholderText("Voltage (V)")
        self.voltage_input.setFixedWidth(90)

        self.set_button = QPushButton("Set Voltage")
        self.set_button.clicked.connect(self.set_voltage)

        row.addWidget(self.voltage_input)
        row.addWidget(self.set_button)

        layout.addLayout(row)

        # Off button
        self.off_button = QPushButton("Turn Off")
        self.off_button.clicked.connect(self.turn_off)
        layout.addWidget(self.off_button)

        # Initialize button color
        self.update_off_button_color()

    def update_off_button_color(self):
        # Green if ON, red if OFF
        color = "lightgreen" if self.state else "lightcoral"
        self.off_button.setStyleSheet(f"background-color: {color};")

    def set_voltage(self):
        try:
            voltage = float(self.voltage_input.text())
            switch_on(self.device, self.channel, voltage)

            # Mark as ON after setting voltage
            self.state = True
            self.update_off_button_color()

            print(f"{self.device.name} {self.channel} updated to {voltage} V")

        except ValueError:
            print("Invalid voltage entered.")
        except Exception as e:
            print(f"Error setting voltage on {self.device.name} {self.channel}: {e}")

    def turn_off(self):
        try:
            switch_off(self.device, self.channel)
            self.state = False
            self.update_off_button_color()
            print(f"{self.device.name} {self.channel} switched OFF")
        except Exception as e:
            print(f"Error turning off {self.device.name} {self.channel}: {e}")

class HeaterSetWidget(QWidget):  # Creates inputs for heaters, at a set temp which is maintained using PID
    def __init__(self, device, channel):
        super().__init__()
        self.device = device
        self.channel = channel
        self.state = False  # OFF by default

        layout = QVBoxLayout()
        self.setLayout(layout)



        # Label for channel
        label = QLabel(f"HEATER ({channel})")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # Voltage input row
        row = QHBoxLayout()

        self.temperature_input = QLineEdit()
        self.temperature_input.setPlaceholderText("Temperature (K)")
        self.temperature_input.setFixedWidth(90)

        self.set_button = QPushButton("Set Temp PID")
        self.set_button.clicked.connect(self.set_temp)

        row.addWidget(self.temperature_input)
        row.addWidget(self.set_button)

        layout.addLayout(row)

        # Off button
        self.off_button = QPushButton("Turn Off")
        self.off_button.clicked.connect(self.turn_off)
        layout.addWidget(self.off_button)

        # Initialize button color
        self.update_off_button_color()

    def update_off_button_color(self):
        # Green if ON, red if OFF
        color = "lightgreen" if self.state else "lightcoral"
        self.off_button.setStyleSheet(f"background-color: {color};")

    def set_temp(self):
        try:
            temperature = float(self.temperature_input.text())
            self.device.write_setpoint(self.channel, temperature)
            heater_on(self.device, self.channel)
            # Mark as ON after setting temperature
            self.state = True
            self.update_off_button_color()

            print(f"{self.device.name} {self.channel} updated to {temperature} V")

        except ValueError:
            print("Invalid temperature entered.")
        except Exception as e:
            print(f"Error setting temperature on {self.device.name} {self.channel}: {e}")

    def turn_off(self):
        try:
            heater_off(self.device, self.channel)
            self.state = False
            self.update_off_button_color()
            print(f"{self.device.name} {self.channel} switched OFF")
        except Exception as e:
            print(f"Error turning off {self.device.name} {self.channel}: {e}")



class HeaterButton(QPushButton):  # Buttons for heaters, these are toggleable, on/off
    def __init__(self, device, channel, initial_state=False):
        super().__init__()
        self.device = device
        self.channel = channel
        self.state = initial_state

        self.setCheckable(True)
        self.setChecked(initial_state)
        self.setText(f"HEATER \n ({channel})")
        self.update_color()

        self.clicked.connect(self.toggle_heater)

    def update_color(self):
        self.setStyleSheet(
            "background-color: lightgreen;" if self.state else "background-color: lightcoral;"
        )

    def toggle_heater(self):
        try:
            if not self.state:
                heater_on(self.device, self.channel)
                self.state = True
            else:
                heater_off(self.device, self.channel)
                self.state = False
            self.update_color()

        except Exception as e:
            print(f"Error toggling heater {self.device.name} {self.channel}: {e}")


class StillHeater(QWidget):
    def __init__(self, device, channel):
        super().__init__()
        self.device = device
        self.channel = channel
        self.state = False  # OFF by default

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Label for channel
        label = QLabel(f"STILL HEATER ({channel})")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # Voltage input row
        row = QHBoxLayout()

        self.percent_input = QLineEdit()
        self.percent_input.setPlaceholderText("Percentage of max voltage")
        self.percent_input.setFixedWidth(90)

        self.set_button = QPushButton("Set Value")
        self.set_button.clicked.connect(self.set_percentage)

        row.addWidget(self.percent_input)
        row.addWidget(self.set_button)

        layout.addLayout(row)

        # Off button
        self.off_button = QPushButton("Turn Off")
        self.off_button.clicked.connect(self.turn_off)
        layout.addWidget(self.off_button)

        # Initialize button color
        self.update_off_button_color()

    def update_off_button_color(self):
        # Green if ON, red if OFF
        color = "lightgreen" if self.state else "lightcoral"
        self.off_button.setStyleSheet(f"background-color: {color};")

    def set_percentage(self):
        try:
            percentage = float(self.percent_input.text())
            self.device.set_still_voltage(percentage)

            # Mark as ON after setting voltage
            self.state = True
            self.update_off_button_color()

            print(f"{self.device.name} {self.channel} updated to {percentage} %")

        except ValueError:
            print("Invalid percent of max voltage entered.")
        except Exception as e:
            print(f"Error setting voltage on {self.device.name} {self.channel}: {e}")

    def turn_off(self):
        try:
            self.device.set_still_voltage(0)
            self.state = False
            self.update_off_button_color()
            print(f"{self.device.name} {self.channel} switched OFF")
        except Exception as e:
            print(f"Error turning off {self.device.name} {self.channel}: {e}")


class ControlPanel(QWidget):  # Creates the control panel
    def __init__(self, devices):
        super().__init__()
        self.setWindowTitle("Heat Switch & Heater Control")
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        for dev_name, dev in devices.items(): # Columns of devices, with controls of each channel under label

            device_layout = QVBoxLayout()
            label = QLabel(dev_name)
            label.setAlignment(Qt.AlignCenter)
            device_layout.addWidget(label)

            channel_map = self.get_channels_for_device(dev_name)

            for channel, ch_type in channel_map.items():
                row = QHBoxLayout()

                if ch_type == "still_heater":
                    row.addWidget(StillHeater(dev, channel))

                elif ch_type == "switch":
                    row.addWidget(SwitchWidget(dev, channel))

                elif ch_type == "heater":
                    row.addWidget(HeaterSetWidget(dev, channel))

                device_layout.addLayout(row)

            self.main_layout.addLayout(device_layout)

    @staticmethod
    def get_channels_for_device(dev_name):
        """
        Returns dict: {channel: "switch" | "heater" | "still_heater"}
        """

        if dev_name in ("CTC100A", "CTC100B"):
            return {
                "4puheat": "heater",
                "3puheat": "heater",
                "4swheat": "switch",
                "3swheat": "switch",
                "AIO3": "switch",
                "AIO4": "switch",
            }
        
        elif dev_name in ("LakeshoreModel372"):
            return {
                "still" : "still_heater"
            }

        return {}


if __name__ == "__main__":
    devices = connect_devices()
    app = QApplication(sys.argv)
    panel = ControlPanel(devices)
    panel.show()
    sys.exit(app.exec_())
