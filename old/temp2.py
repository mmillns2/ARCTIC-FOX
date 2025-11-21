import time
import serial
import numpy as np
import serial.tools.list_ports
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from CTC100 import CTC100Device
from lakeshore224device import LakeShore224Device
from lakeshore372device import LakeShore372Device

DEBUG = False   # Set True to print sensor values

# -----------------------------------------------------------
# DEVICE CONNECTION
# -----------------------------------------------------------
def connect_devices():
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
def read_temperatures(devices):
    readings = {}

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
# CREATE PLOTTING WINDOWS
# -----------------------------------------------------------
def setup_plots(groups):
    figs, axes, lines, data, legends = {}, {}, {}, {}, {}

    for win_name, sensors in groups.items():
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
        data[win_name]['times'] = []

        for ch in sensors:
            (line,) = ax.plot([], [], lw=2, label=ch)
            lines[win_name].append(line)

        legends[win_name] = ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1.0), prop={'size': 11})

    return figs, axes, lines, data, legends

# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
def main():
    devices = connect_devices()
    if not devices:
        print("No devices found.")
        return

    temps = read_temperatures(devices)

    # -------------------------------------------------------
    # GROUPING
    # -------------------------------------------------------
    groups = {}

    # A side group
    A = []
    if "CTC100A" in temps:
        A += temps["CTC100A"].keys()
    if "Lakeshore224" in temps:
        A += ["4HePotA", "3HePotA"]
    groups["A Side (CTC100A + He Pots A)"] = A

    # B side group
    B = []
    if "CTC100B" in temps:
        B += temps["CTC100B"].keys()
    if "Lakeshore224" in temps:
        B += ["4HePotB", "3HePotB"]
    groups["B Side (CTC100B + He Pots B)"] = B

    # DR System group
    dr = []
    if "Lakeshore372" in temps:
        dr += temps["Lakeshore372"].keys()
    if "Lakeshore224" in temps:
        dr += ["Condenser"]
    groups["DR System (MC + Still + Condenser)"] = dr

    # 4K plate alone
    groups["4 K Plate"] = ["4K Plate"]

    # Create windows
    figs, axes, lines, data, legends = setup_plots(groups)

    window_seconds = 300
    start_time = time.time()

    # -------------------------------------------------------
    # UPDATE FUNCTION (FIXED)
    # -------------------------------------------------------
    def update(frame):
        current_time = time.time() - start_time
        temps = read_temperatures(devices)

        for win_name, sensors in groups.items():
            data[win_name]["times"].append(current_time)

            for i, ch in enumerate(sensors):
                # Correct sensor-device mapping
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

                data[win_name][ch].append(val)

                times = data[win_name]["times"]
                yvals = data[win_name][ch]

                # Sliding window
                if window_seconds:
                    start_idx = next((j for j, t in enumerate(times) if t >= current_time - window_seconds), 0)
                    xdata = times[start_idx:]
                    ydata = yvals[start_idx:]
                else:
                    xdata = times
                    ydata = yvals

                lines[win_name][i].set_data(xdata, ydata)

                # Gradient (K/min)
                grad = (ydata[-1] - ydata[0]) / ((xdata[-1] - xdata[0]) / 60) if len(ydata) > 1 else 0

                # Update legend
                legends[win_name].texts[i].set_text(f"{ch}\n {ydata[-1]:.3f} K\n {grad:.4f} K/min")

            # Update axes
            ax = axes[win_name]
            if window_seconds:
                ax.set_xlim(max(0, current_time - window_seconds), current_time)
            else:
                ax.set_xlim(0, current_time)

            ax.relim()
            ax.autoscale_view()

        return []

    # -------------------------------------------------------
    # Animate ALL figures
    # -------------------------------------------------------
    anims = []
    for fig in figs.values():
        anim = animation.FuncAnimation(fig, update, interval=2000, blit=False)
        anims.append(anim)

    plt.show()

# Run
if __name__ == "__main__":
    main()

