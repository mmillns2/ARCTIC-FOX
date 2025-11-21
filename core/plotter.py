import time
import serial
import numpy as np
import serial.tools.list_ports
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from threading import Thread, Lock

from devices.device import device_lock
from devices.CTC100 import CTC100Device
from devices.lakeshore224device import LakeShore224Device
from devices.lakeshore372device import LakeShore372Device

DEBUG = False

class TemperaturePlotter(Thread):
    def __init__(self, window_seconds=300, interval=2000):
        super().__init__()
        self.window_seconds = window_seconds
        self.interval = interval

        self.devices = {}
        self.groups = {}
        self.figs = {}
        self.axes = {}
        self.lines = {}
        self.data = {}
        self.legends = {}
        self.anims = []
        self.running = True

    # -----------------------------------------------------------
    # DEVICE CONNECTION
    # -----------------------------------------------------------
    def connect_devices(self):
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
                model224 = LakeShore224Device(port=device.device, name='Lakeshore224')
            elif '372' in device.description:
                model372 = LakeShore372Device(port=device.device, name='Lakeshore372')

        connected = {
            "CTC100A": ctc100A,
            "CTC100B": ctc100B,
            "Lakeshore224": model224,
            "Lakeshore372": model372,
        }

        return {k: v for k, v in connected.items() if v is not None}

    # -----------------------------------------------------------
    # TEMPERATURE READOUT
    # -----------------------------------------------------------
    def read_temperatures(self):
        devices = self.devices
        readings = {}

        with device_lock:
            if "CTC100A" in devices:
                dev = devices["CTC100A"]
                readings["CTC100A"] = {
                    "4switchA": dev.get_temperature("4switch"),
                    "4pumpA": dev.get_temperature("4pump"),
                    "3switchA": dev.get_temperature("3switch"),
                    "3pumpA": dev.get_temperature("3pump"),
                }

            if "CTC100B" in devices:
                dev = devices["CTC100B"]
                readings["CTC100B"] = {
                    "4switchB": dev.get_temperature("4switch"),
                    "4pumpB": dev.get_temperature("4pump"),
                    "3switchB": dev.get_temperature("3switch"),
                    "3pumpB": dev.get_temperature("3pump"),
                }

            if "Lakeshore224" in devices:
                dev = devices["Lakeshore224"]
                readings["Lakeshore224"] = {
                    "4HePotA": dev.get_temperature("C1"),
                    "3HePotA": dev.get_temperature("B"),
                    "4HePotB": dev.get_temperature("C2"),
                    "3HePotB": dev.get_temperature("D1"),
                    "Condenser": dev.get_temperature("A"),
                    "50K Plate": dev.get_temperature("D2"),
                    "4K Plate": dev.get_temperature("D3"),
                }

            if "Lakeshore372" in devices:
                dev = devices["Lakeshore372"]
                readings["Lakeshore372"] = {
                    "MC": dev.get_temperature("1"),
                    "Still": dev.get_temperature("A"),
                }

        return readings

    # -----------------------------------------------------------
    # PLOT SETUP
    # -----------------------------------------------------------
    def setup_plots(self):
        figs, axes, lines, data, legends = {}, {}, {}, {}, {}

        for win_name, sensors in self.groups.items():
            fig, ax = plt.subplots(figsize=(8, 5))
            fig.canvas.manager.set_window_title(win_name)
            ax.set_title(win_name)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Temperature (K)")
            ax.grid(True)

            figs[win_name] = fig
            axes[win_name] = ax
            lines[win_name] = []
            data[win_name] = {ch: [] for ch in sensors}
            data[win_name]["times"] = []

            for ch in sensors:
                (line,) = ax.plot([], [], lw=2, label=ch)
                lines[win_name].append(line)

            legends[win_name] = ax.legend(
                loc='upper left',
                bbox_to_anchor=(1.02, 1.0),
                prop={'size': 11},
            )

        self.figs = figs
        self.axes = axes
        self.lines = lines
        self.data = data
        self.legends = legends

    # -----------------------------------------------------------
    # UPDATE FUNCTION
    # -----------------------------------------------------------
    def update(self, frame):
        if not self.running:
            return

        current_time = time.time() - self.start_time
        temps = self.read_temperatures()

        for win_name, sensors in self.groups.items():
            self.data[win_name]["times"].append(current_time)

            for i, ch in enumerate(sensors):
                val = None
                if "CTC100A" in temps and ch in temps["CTC100A"]:
                    val = temps["CTC100A"][ch]
                elif "CTC100B" in temps and ch in temps["CTC100B"]:
                    val = temps["CTC100B"][ch]
                elif "Lakeshore224" in temps and ch in temps["Lakeshore224"]:
                    val = temps["Lakeshore224"][ch]
                elif "Lakeshore372" in temps and ch in temps["Lakeshore372"]:
                    val = temps["Lakeshore372"][ch]

                if val is None or (isinstance(val, float) and np.isnan(val)):
                    continue

                if DEBUG:
                    print(f"{win_name}: {ch} = {val}")

                self.data[win_name][ch].append(val)

                times = self.data[win_name]["times"]
                yvals = self.data[win_name][ch]

                if self.window_seconds:
                    start_idx = next(
                        (j for j, t in enumerate(times) if t >= current_time - self.window_seconds), 0
                    )
                    xdata = times[start_idx:]
                    ydata = yvals[start_idx:]
                else:
                    xdata = times
                    ydata = yvals

                self.lines[win_name][i].set_data(xdata, ydata)

                grad = 0
                if len(ydata) > 1:
                    grad = (ydata[-1] - ydata[0]) / ((xdata[-1] - xdata[0]) / 60)

                self.legends[win_name].texts[i].set_text(
                    f"{ch}\n {ydata[-1]:.3f} K\n {grad:.4f} K/min"
                )

            ax = self.axes[win_name]
            if self.window_seconds:
                ax.set_xlim(max(0, current_time - self.window_seconds), current_time)
            else:
                ax.set_xlim(0, current_time)

            ax.relim()
            ax.autoscale_view()

        return []

    # -----------------------------------------------------------
    # THREAD ENTRY POINT
    # -----------------------------------------------------------
    def run(self):
        self.devices = self.connect_devices()
        if not self.devices:
            print("No devices found.")
            return

        init_read = self.read_temperatures()

        # ------------------ GROUPING ------------------
        A = []
        if "CTC100A" in init_read:
            A += init_read["CTC100A"].keys()
        if "Lakeshore224" in init_read:
            A += ["4HePotA", "3HePotA"]
        self.groups["A Side (CTC100A + He Pots A)"] = A

        B = []
        if "CTC100B" in init_read:
            B += init_read["CTC100B"].keys()
        if "Lakeshore224" in init_read:
            B += ["4HePotB", "3HePotB"]
        self.groups["B Side (CTC100B + He Pots B)"] = B

        dr = []
        if "Lakeshore372" in init_read:
            dr += init_read["Lakeshore372"].keys()
        if "Lakeshore224" in init_read:
            dr += ["Condenser"]
        self.groups["DR System (MC + Still + Condenser)"] = dr

        self.groups["4 K Plate"] = ["4K Plate"]

        self.setup_plots()

        self.start_time = time.time()

        for fig in self.figs.values():
            anim = animation.FuncAnimation(fig, self.update, interval=self.interval, blit=False)
            self.anims.append(anim)

        plt.show()

    def stop(self):
        self.running = False
