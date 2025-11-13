import time
import serial.tools.list_ports
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# ----------------------------
# 1. Device connection (run once)
# ----------------------------
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
            model224 = LakeShore224Device(port=device.device, name='LakeshoreModel224')
        elif '372' in device.description:
            model372 = LakeShore372Device(port=device.device, name='LakeshoreModel372')

    connected = {
        "CTC100A": ctc100A,
        "CTC100B": ctc100B,
        "LakeshoreModel224": model224,
        "LakeshoreModel372": model372
    }

    # Remove None entries
    return {k: v for k, v in connected.items() if v is not None}


# ----------------------------
# 2. Poll temperatures each frame
# ----------------------------
def read_temperatures(devices):
    readings = {}

    if "CTC100A" in devices:
        dev = devices["CTC100A"]
        readings["CTC100A"] = {
            "4switch": dev.get_temperature("4switch"),
            "4pump": dev.get_temperature("4pump"),
            "3switch": dev.get_temperature("3switch"),
            "3pump": dev.get_temperature("3pump"),
        }

    if "CTC100B" in devices:
        dev = devices["CTC100B"]
        readings["CTC100B"] = {
            "4switch": dev.get_temperature("4switch"),
            "4pump": dev.get_temperature("4pump"),
            "3switch": dev.get_temperature("3switch"),
            "3pump": dev.get_temperature("3pump"),
        }

    if "LakeshoreModel224" in devices:
        dev = devices["LakeshoreModel224"]
        readings["LakeshoreModel224"] = {
            "C1": dev.get_temperature("C1"),
            "B": dev.get_temperature("B"),
            "C2": dev.get_temperature("C2"),
            "D1": dev.get_temperature("D1"),
            "A": dev.get_temperature("A"),
            "D2": dev.get_temperature("D2"),
            "D3": dev.get_temperature("D3"),
        }

    if "LakeshoreModel372" in devices:
        dev = devices["LakeshoreModel372"]
        readings["LakeshoreModel372"] = {
            "1": dev.get_temperature("1"),
            "A": dev.get_temperature("A"),
        }

    return readings


# ----------------------------
# 3. Setup plots
# ----------------------------
def setup_plots(device_data):
    num_devices = len(device_data)
    nrows = (num_devices + 1) // 2
    ncols = 2 if num_devices > 1 else 1
    fig, axes = plt.subplots(nrows, ncols, figsize=(12, nrows*3))
    if num_devices == 1:
        axes = [axes]
    else:
        axes = axes.flatten()
    
    lines = {}
    data = {}

    for ax, (dev_name, sensors) in zip(axes, device_data.items()):
        ax.set_title(dev_name)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Temperature (K)")
        ax.set_ylim(0, 300)  # adjust for expected range
        lines[dev_name] = []
        data[dev_name] = {ch: [] for ch in sensors.keys()}
        data[dev_name]['times'] = []
        for ch in sensors.keys():
            (line,) = ax.plot([], [], lw=2, label=ch)
            lines[dev_name].append(line)
        ax.legend()
    
    plt.tight_layout()
    return fig, axes, lines, data


# ----------------------------
# 4. Animate updates
# ----------------------------
def main():
    devices = connect_devices()
    if not devices:
        print("No devices found. Exiting.")
        return

    # Initial read to get channels
    initial_data = read_temperatures(devices)
    fig, axes, lines, data = setup_plots(initial_data)

    # Sliding window in seconds (None = full history)
    window_seconds = 60

    start_time = time.time()

    def update(frame):
        current_time = time.time() - start_time
        readings = read_temperatures(devices)

        for dev_name, sensors in readings.items():
            data[dev_name]['times'].append(current_time)
            for i, (ch, temp) in enumerate(sensors.items()):
                data[dev_name][ch].append(temp)

                # Apply sliding window if set
                if window_seconds:
                    # Find the index where time > current_time - window_seconds
                    times = data[dev_name]['times']
                    start_idx = 0
                    for j, t in enumerate(times):
                        if t >= current_time - window_seconds:
                            start_idx = j
                            break
                    xdata = times[start_idx:]
                    ydata = data[dev_name][ch][start_idx:]
                else:
                    xdata = data[dev_name]['times']
                    ydata = data[dev_name][ch]

                lines[dev_name][i].set_data(xdata, ydata)

            # Update x-axis
            ax = axes[list(devices.keys()).index(dev_name)]
            if window_seconds:
                ax.set_xlim(max(0, current_time - window_seconds), current_time)
            else:
                ax.set_xlim(0, current_time)
            ax.relim()
            ax.autoscale_view(scalex=False, scaley=True)

        return [l for sub in lines.values() for l in sub]

    ani = animation.FuncAnimation(fig, update, interval=2000, blit=False)
    plt.show()


if __name__ == "__main__":
    main()

