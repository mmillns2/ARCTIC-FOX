from controller_server import DeviceControllerServer
from remote_readout import plot_data, DBReader
from device import get_channels_for_device
from flask import Flask, render_template, request, jsonify, Response
from sql import SQL

import matplotlib.pyplot as plt
import io
import queue

HOST = "127.0.0.1"
PORT = 8084

# Global dictionary storing last set values for all devices/channels
# Keys are tuples: (device_name, channel_name)
LAST_VALUES = {}

# Stores heater/switch/still ON/OFF state
# Keys: (device, channel) → "on" or "off"
LAST_STATES = {}

app = Flask(__name__, template_folder="templates")

controller = DeviceControllerServer(HOST, PORT)
devices = controller.get_devices()

# ROUTES
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


# SWITCH CONTROL
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


# HEATER CONTROL
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


# STILL HEATER CONTROL
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

# plotting
PLOT_MAPPING = {}
plot_id = 1

for dev_name in devices.keys():
    # use channels from plot_data (ignore 'times')
    channels = [k for k in plot_data.get(dev_name, {}) if k != "times"]
    if channels:
        PLOT_MAPPING[plot_id] = (dev_name, channels)
        plot_id += 1

print("Dynamic PLOT_MAPPING:", PLOT_MAPPING)

# create sql database instance
sql = SQL(debug=False, options=["localhost", "axion_writer", 8082, "axion_db"])

plot_queue = queue.Queue()
db_reader = DBReader(sql, plot_queue)
db_reader.start()   # start reader thread

@app.route("/plot/<int:plot_id>.png")
def plot_png(plot_id):

    if plot_id not in PLOT_MAPPING:
        return "Invalid plot ID", 404

    device, channels = PLOT_MAPPING[plot_id]

    # Get latest DB data
    latest_plot_data = None
    try:
        while True:
            latest_plot_data = plot_queue.get_nowait()
    except queue.Empty:
        pass

    if latest_plot_data is None:
        latest_plot_data = plot_data

    # Extract time + channel data for this device
    device_data = latest_plot_data.get(device, {})
    times = device_data.get("times", [])

    ys_dict = {
        ch: device_data.get(ch, [])
        for ch in channels
    }

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
        fontsize='small'
    )

    # Map legend labels to indices
    label_to_index = {t.get_text(): i for i, t in enumerate(leg.texts)}

    # Modify legend text: temperature + gradient
    for ch, ys in ys_dict.items():
        if times and ys:
            current_temp = ys[-1]
            idx = label_to_index[ch]

            if len(times) > 11:
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

@app.route("/api/plotdata")
def api_plotdata():

    # Get latest DB data
    latest_plot_data = None
    try:
        while True:
            latest_plot_data = plot_queue.get_nowait()
    except queue.Empty:
        pass

    if latest_plot_data is None:
        latest_plot_data = plot_data

    result = {}
    for pid, (dev_name, channels) in PLOT_MAPPING.items():
        result[pid] = {
            ch: latest_plot_data.get(dev_name, {}).get(ch, [])
            for ch in channels
        }

    return jsonify(result)

@app.route("/display/<device_name>")
def display_device(device_name):
    plot_ids = [
        pid for pid, (dname, _) in PLOT_MAPPING.items()
        if dname == device_name
    ]
    if not plot_ids:
        return f"No plots found for {device_name}", 404

    return render_template("display_single.html",
                           title=device_name,
                           plots=plot_ids)

@app.route("/display")
def display_all():
    return render_template("display.html",
                           plots=list(PLOT_MAPPING.keys()))


# Run server
if __name__ == "__main__":
    # run webserver on port 8083
    app.run(debug=False, host="0.0.0.0", port=8085)

