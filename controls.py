import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from cooldown_loop_dilution_v2 import switch_on, switch_off, heater_on, heater_off
from CTC100 import CTC100Device
from lakeshore224device import LakeShore224Device
from lakeshore372device import LakeShore372Device
import serial


def connect_devices(): # Connects to devices
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
        "LakeshoreModel224": model224,
        "LakeshoreModel372": model372
    }

    return {k: v for k, v in connected.items() if v is not None}


class SwitchButton(QPushButton): # Makes switch buttons
    def __init__(self, device, channel, initial_state=False):
        super().__init__()
        self.device = device
        self.channel = channel
        self.state = initial_state

        self.setCheckable(True)
        self.setChecked(initial_state)
        self.setText(f"{channel}\nSWITCH")
        self.update_color()

        self.clicked.connect(self.toggle_switch)

    def update_color(self):
        self.setStyleSheet(
            "background-color: lightgreen;" if self.state else "background-color: lightcoral;"
        )

    def toggle_switch(self):
        try:
            if not self.state:
                switch_on(self.device, self.channel)
                self.state = True
            else:
                switch_off(self.device, self.channel)
                self.state = False
            self.update_color()

        except Exception as e:
            print(f"Error toggling switch {self.device.name} {self.channel}: {e}")


class HeaterButton(QPushButton): # Buttons for heaters
    def __init__(self, device, channel, initial_state=False):
        super().__init__()
        self.device = device
        self.channel = channel
        self.state = initial_state

        self.setCheckable(True)
        self.setChecked(initial_state)
        self.setText(f"{channel}\nHEATER")
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


class ControlPanel(QWidget): # Creates the control panel
    def __init__(self, devices):
        super().__init__()
        self.setWindowTitle("Heat Switch & Heater Control")
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        for dev_name, dev in devices.items():

            device_layout = QVBoxLayout()
            label = QLabel(dev_name)
            label.setAlignment(Qt.AlignCenter)
            device_layout.addWidget(label)

            channel_map = self.get_channels_for_device(dev_name)

            for channel, ch_type in channel_map.items():
                row = QHBoxLayout()

                if ch_type == "switch": # Tells us what type of button the channel needs
                    row.addWidget(SwitchButton(dev, channel))

                elif ch_type == "heater":
                    row.addWidget(HeaterButton(dev, channel))

                elif ch_type == "both":
                    row.addWidget(SwitchButton(dev, channel))
                    row.addWidget(HeaterButton(dev, channel))

                device_layout.addLayout(row)

            self.main_layout.addLayout(device_layout)

    @staticmethod
    def get_channels_for_device(dev_name): # Maps channels
        """
        Returns dict: {channel: "switch" | "heater" | "both"}
        Update this mapping to match your cryostat wiring.
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

        # if dev_name == "LakeshoreModel224": ...

        return {}


if __name__ == "__main__": # Runs code
    devices = connect_devices()
    app = QApplication(sys.argv)
    panel = ControlPanel(devices)
    panel.show()
    sys.exit(app.exec_())
