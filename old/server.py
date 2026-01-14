"""
server.py

Flask app that:
 - auto-discovers devices via connect_devices()
 - serves /controller (dynamic control panel)
 - serves /display (live plot)
 - exposes AJAX endpoints for all controls that map to your existing functions
    (switch_on, switch_off, heater_on, heater_off, device.write_setpoint, device.set_still_voltage)
 - has safe mocks if hardware libs are not available so you can run/test without devices
"""

from flask import Flask, render_template, request, jsonify, Response
import threading, time, io
import random
import sys

from cooldown_loop_dilution_v2 import switch_on, switch_off, heater_on, heater_off
from CTC100 import CTC100Device
from lakeshore224device import LakeShore224Device
from lakeshore372device import LakeShore372Device
import serial

from hardware_reader import HardwareTemperatureReader
from controller import hardware_lock
from controller import DeviceController
from device import connect_devices

import matplotlib
matplotlib.use("Agg")   # non-GUI backend, works for generating PNGs in the background

import matplotlib.pyplot as plt

# Global dictionary storing last set values for all devices/channels
# Keys are tuples: (device_name, channel_name)
LAST_VALUES = {}

# Stores heater/switch/still ON/OFF state
# Keys: (device, channel) → "on" or "off"
LAST_STATES = {}

# load devices and create controller
devices = connect_devices()
print("Detected devices:", list(devices.keys()))
controller = DeviceController(devices)

# create the reader
temp_reader = HardwareTemperatureReader(devices)

# temp hardware lock

app = Flask(__name__, template_folder="templates")

# ---------------------------------------------------------------------
# Channel mapping function (same mapping you used in PyQt)
# ---------------------------------------------------------------------
def get_channels_for_device(dev_name):
    if dev_name in ("CTC100A", "CTC100B"):
        return {
            "4puheat": "heater",
            "3puheat": "heater",
            "4swheat": "switch",
            "3swheat": "switch",
            "AIO3": "switch",
            "AIO4": "switch",
        }
    elif dev_name in ("LakeshoreModel372", "Lakeshore372"):
        return {"still": "still_heater"}
    # If you later add Lakeshore224 mapping, add here
    return {}

# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------
@app.route("/")
def root():
    # simple redirect to /display (optional) or present links
    return """
    <h2>ARCTIC FOX interface</h2>
    <p><a href="/display">Display (live plot)</a></p>
    <p><a href="/controller">Controller (control panel)</a></p>
    """

@app.route("/display")
def display():
    return render_template("display.html")

@app.route("/controller")
def controller_page():
    devices_context = {}
    for dev_name, dev in devices.items():
        channels = get_channels_for_device(dev_name)
        devices_context[dev_name] = {"channels": channels}

    return render_template(
        "controller.html",
        devices=devices_context,
        last_values=LAST_VALUES,
        last_states=LAST_STATES
    )

@app.route("/api/controller_state")
def api_controller_state():
    # Convert tuple keys to strings so JSON can send them
    values = {f"{dev}::{ch}": val for (dev, ch), val in LAST_VALUES.items()}
    states = {f"{dev}::{ch}": st for (dev, ch), st in LAST_STATES.items()}
    return jsonify({"values": values, "states": states})


# ---------------------------------------------------------------------
# CONTROL AJAX endpoints - accept JSON POSTs
# ---------------------------------------------------------------------

# -----------------------------
# SWITCH CONTROL
# -----------------------------

@app.route("/api/set_switch_voltage", methods=["POST"])
def api_set_switch():
    data = request.json
    dev = data["device"]
    ch = data["channel"]
    value = float(data["value"])

    LAST_VALUES[(dev, ch)] = value      # STORE VALUE
    LAST_STATES[(dev, ch)] = "on"

    controller.set_switch_voltage(dev, ch, value)
    return jsonify(status="ok")

@app.route("/api/turn_off_switch", methods=["POST"])
def api_switch_off():
    data = request.json
    dev = data["device"]
    ch = data["channel"]

    LAST_VALUES[(dev, ch)] = None       # CLEAR VALUE
    LAST_STATES[(dev, ch)] = "off"

    controller.turn_off_switch(dev, ch)
    return jsonify(status="ok")


# -----------------------------
# HEATER CONTROL
# -----------------------------
@app.route("/api/set_heater_temp", methods=["POST"])
def api_set_heater_temp():
    data = request.json
    dev = data["device"]
    ch = data["channel"]
    value = float(data["value"])

    LAST_VALUES[(dev, ch)] = value      # STORE VALUE
    LAST_STATES[(dev, ch)] = "on"

    controller.set_heater_temperature(dev, ch, value)
    return jsonify(status="ok")

@app.route("/api/turn_off_heater", methods=["POST"])
def api_heater_off():
    data = request.json
    dev = data["device"]
    ch = data["channel"]

    LAST_VALUES[(dev, ch)] = None       # CLEAR VALUE
    LAST_STATES[(dev, ch)] = "off"

    controller.turn_off_heater(dev, ch)
    return jsonify(status="ok")

# -----------------------------
# STILL HEATER CONTROL
# -----------------------------
@app.route("/api/set_still_percentage", methods=["POST"])
def api_set_still():
    data = request.json
    dev = data["device"]
    ch = data["channel"]
    value = float(data["value"])

    LAST_VALUES[(dev, ch)] = value      # STORE VALUE
    LAST_STATES[(dev, ch)] = "on"

    controller.set_still_percentage(dev, ch, value)
    return jsonify(status="ok")

@app.route("/api/turn_off_still", methods=["POST"])
def api_still_off():
    data = request.json
    dev = data["device"]
    ch = data["channel"]

    LAST_VALUES[(dev, ch)] = None       # CLEAR VALUE
    LAST_STATES[(dev, ch)] = "off"

    controller.turn_off_still(dev, ch)
    return jsonify(status="ok")


# ---------------------------------------------------------------------
# Live plot backend — FOUR independent data streams
# ---------------------------------------------------------------------

# new structure:
# plot_data[device][channel] = list of values
# plot_data[device]["times"] = list of timestamps


plot_data = {
    "CTC100A": {"times": [], "4switchA": [], "4pumpA": [], "3switchA": [], "3pumpA": []},
    "CTC100B": {"times": [], "4switchB": [], "4pumpB": [], "3switchB": [], "3pumpB": []},
    "Lakeshore372": {"times": [], "MC": [], "Still": []},
    "Lakeshore224": {"times": [], "4HePotA": [], "3HePotA": [], "4HePotB": [], "3HePotB": [], "Condenser": [], "50K": [], "4K": []}
}
# -------------------------
# Dynamic plot mapping
# -------------------------
PLOT_MAPPING = {}
plot_id = 1

for dev_name in temp_reader.devices.keys():
    # use channels from plot_data (ignore 'times')
    channels = [k for k in plot_data.get(dev_name, {}) if k != "times"]
    if channels:
        PLOT_MAPPING[plot_id] = (dev_name, channels)
        plot_id += 1

print("Dynamic PLOT_MAPPING:", PLOT_MAPPING)


plot_lock = threading.Lock()

def background_update_thread():
    start_time = time.time()

    while True:
        with hardware_lock:
            temps = temp_reader.read_temperatures()

        t = time.time() - start_time

        with plot_lock:
            for dev_name, sensors in temps.items():

                # Ensure structure exists
                if dev_name not in plot_data:
                    plot_data[dev_name] = {"times": []}
                if "times" not in plot_data[dev_name]:
                    plot_data[dev_name]["times"] = []

                plot_data[dev_name]["times"].append(t)

                for ch, value in sensors.items():
                    if ch not in plot_data[dev_name]:
                        plot_data[dev_name][ch] = []
                    plot_data[dev_name][ch].append(value)

                # window = 300 seconds
                window = 300
                times = plot_data[dev_name]["times"]
                start = next((i for i,x in enumerate(times) if x >= t - window), 0)

                # trim to last 300 seconds
                for ch in plot_data[dev_name]:
                    plot_data[dev_name][ch] = plot_data[dev_name][ch][start:]

        time.sleep(2)

threading.Thread(target=background_update_thread, daemon=True).start()

"""
@app.route("/plot/<int:plot_id>.png")
def plot_png(plot_id):
    import matplotlib.pyplot as plt

    if plot_id not in plot_data:
        return "Invalid plot ID", 404

    with plot_lock:
        ys = plot_data[plot_id][:]
    xs = list(range(len(ys)))

    buf = io.BytesIO()

    fig, ax = plt.subplots(figsize=(6, 3))   # a bit larger

    if xs and ys:
        ax.plot(xs, ys)
        ax.set_xlabel("sample #")

    ax.set_title(f"Plot {plot_id}")
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)

    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")
"""



# Backwards-compatible small endpoint returning the 4 numeric single traces (if you still want them)
@app.route("/plot/<int:plot_id>.png")
def plot_png(plot_id):
    if plot_id not in PLOT_MAPPING:
        return "Invalid plot ID", 404

    device, channels = PLOT_MAPPING[plot_id]

    with plot_lock:
        times = plot_data.get(device, {}).get("times", [])
        ys_dict = {ch: plot_data[device].get(ch, []) for ch in channels}

    buf = io.BytesIO()
    fig, ax = plt.subplots(figsize=(6, 3))

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Temperature (K)")
    ax.grid(True)
    ax.set_title(f"{device}")

    for ch, ys in ys_dict.items():
        if times and ys:
            ax.plot(times, ys, label=ch)

    leg = ax.legend(
        loc='upper left',
        bbox_to_anchor=(1.02, 1),
        fontsize = 'small'
    )

    label_to_index = {t.get_text(): i for i, t in enumerate(leg.texts)}

    for ch, ys in ys_dict.items():
        if times and ys:
            current_temp = ys[-1]
            idx = label_to_index[ch]
            if len(times)>11:
                grad = (ys[-1] - ys[-10]) / (times[-1] - times[-10])
                leg.texts[idx].set_text(
                f"{ch}\n {current_temp:.3f}K\n {grad:2f}K/min"
                )
            else:
                leg.texts[idx].set_text(
                f"{ch}\n {current_temp:.3f}K"
                )

    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)

    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")


# -------------------------
# API endpoint for data
# -------------------------
@app.route("/api/plotdata")
def api_plotdata():
    with plot_lock:
        result = {}
        for pid, (dev_name, channels) in PLOT_MAPPING.items():
            result[pid] = {ch: plot_data.get(dev_name, {}).get(ch, []) for ch in channels}
        return jsonify(result)

# -------------------------
# Display routes
# -------------------------
@app.route("/display/<device_name>")
def display_device(device_name):
    # find plot_id for device_name
    plot_ids = [pid for pid, (dname, _) in PLOT_MAPPING.items() if dname == device_name]
    if not plot_ids:
        return f"No plots found for {device_name}", 404
    return render_template("display_single.html", title=device_name, plots=plot_ids)

# -------------------------
# Live display of all plots
# -------------------------
@app.route("/display")
def display_all():
    return render_template("display.html", plots=list(PLOT_MAPPING.keys()))



# ---------------------------------------------------------------------
# Run server
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # 0. Optionally re-scan devices each time you start; devices already scanned at import
    print("Starting Flask server. Devices:", list(devices.keys()))
    app.run(debug=False, host="0.0.0.0", port=8083)
