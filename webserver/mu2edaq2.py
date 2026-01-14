from controller_server import DeviceControllerServer
from remote_readout import plot_data, DBReader
from device import get_channels_for_device
from flask import Flask, render_template, request, jsonify, Response
from sql import SQL

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import io
import queue

from algorithm import Cycle, AlgorithmConfig

algorithm_config = AlgorithmConfig()
cycle_thread = None

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
    <p><a href="/interactive">Display (interactive plot)</a></p>
    <p><a href="/controller">Controller (control panel)</a></p>
    <p><a href="/algorithm">Algorithm (config panel)</a></p>
    """

# ALGORITHM
@app.route("/algorithm")
def algorithm_page():
    return render_template(
        "algorithm.html",
        defaults=algorithm_config
    )

@app.route("/api/algorithm/config", methods=["POST"])
def set_algorithm_config():
    data = request.json
    side = data["side"]  # "A" or "B"
    key = data["key"]
    value = data["value"]

    side_cfg = getattr(algorithm_config, side)
    setattr(side_cfg, key, value)
    return jsonify({"status":"ok"})

@app.route("/api/algorithm/status", methods=["GET"])
def algorithm_status():
    if cycle_thread and cycle_thread.is_alive():
        return jsonify(cycle_thread.get_status())

    return jsonify({
        "running": False,
        "state": "Idle",
        "side": None,
        "elapsed": 0,
        "total": 1
    })

@app.route("/api/algorithm/start", methods=["POST"])
def start_algorithm():
    global cycle_thread
    if cycle_thread is None or not cycle_thread.is_alive():
        cycle_thread = Cycle(controller, algorithm_config, LAST_VALUES, LAST_STATES)
        cycle_thread.start()
    return jsonify({"status":"started"})

@app.route("/api/algorithm/stop", methods=["POST"])
def stop_algorithm():
    if cycle_thread and cycle_thread.is_alive():
        cycle_thread.stop()
    return jsonify({"status":"stopped"})

# PREC0OLING 
@app.route("/api/algorithm/initial_precool", methods=["POST"])
def api_initial_precool():
    data = request.json
    value = float(data["value"])

    algorithm_config.initial_precool.enabled = True
    algorithm_config.initial_precool.value = value

    # Turn OFF all switches
    for dev in ["CTC100A", "CTC100B"]:
        for ch in ["3swheat", "4swheat"]:
            controller.turn_off_switch(dev, ch)
            LAST_VALUES[(dev, ch)] = None
            LAST_STATES[(dev, ch)] = "off"

    # Set ALL heaters to temperature
    for dev in ["CTC100A", "CTC100B"]:
        for ch in ["3puheat", "4puheat"]:
            controller.set_heater_temperature(dev, ch, value)
            LAST_VALUES[(dev, ch)] = value
            LAST_STATES[(dev, ch)] = "on"

    return jsonify(status="enabled")

@app.route("/api/algorithm/pre_cycle_cool", methods=["POST"])
def api_pre_cycle_cool():
    data = request.json
    value = float(data["value"])

    algorithm_config.pre_cycle_cool.enabled = True
    algorithm_config.pre_cycle_cool.value = value

    # Turn OFF all heaters
    for dev in ["CTC100A", "CTC100B"]:
        for ch in ["3puheat", "4puheat"]:
            controller.turn_off_heater(dev, ch)
            LAST_VALUES[(dev, ch)] = None
            LAST_STATES[(dev, ch)] = "off"

    # Turn ON all switches
    for dev in ["CTC100A", "CTC100B"]:
        for ch in ["3swheat", "4swheat"]:
            controller.set_switch_voltage(dev, ch, value)
            LAST_VALUES[(dev, ch)] = value
            LAST_STATES[(dev, ch)] = "on"

    return jsonify(status="enabled")


# MATPLOTLIB DISPLAY
@app.route("/display")
def display():
    return render_template("display.html")

# CONTROLLER 
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

def update_latest_plot_data():
    global latest_plot_snapshot
    try:
        while True:
            # Non-blocking get from queue
            snapshot = plot_queue.get_nowait()
            latest_plot_snapshot = snapshot  # replace with newest snapshot
    except queue.Empty:
        pass

@app.route("/plot/<int:plot_id>.png")
def plot_png(plot_id):
    if plot_id not in PLOT_MAPPING:
        return "Invalid plot ID", 404

    device, channels = PLOT_MAPPING[plot_id]

    # Pull newest snapshot from queue
    update_latest_plot_data()
    if "latest_plot_snapshot" not in globals():
        return "No data yet", 503

    device_data = latest_plot_snapshot.get(device, {})
    times = device_data.get("times", [])

    if not times:
        return "No data yet", 503

    # Convert times to minutes since first timestamp
    t0 = times[0]
    times_min = [(t - t0).total_seconds() / 60.0 for t in times]

    # Sliding 10-minute window
    WINDOW_MIN = 10.0
    if times_min[-1] > WINDOW_MIN:
        t_max = times_min[-1]
        mask = [t >= t_max - WINDOW_MIN for t in times_min]
    else:
        mask = [True] * len(times_min)

    times_plot = [t for t, m in zip(times_min, mask) if m]

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Temperature (K)")
    ax.set_title(device)
    ax.grid(True)

    legend_entries = []

    for ch in channels:
        ys = device_data.get(ch, [])
        if not ys:
            continue

        # Apply mask + filter invalid values
        ys_plot = []
        ts_plot = []

        for t, y, m in zip(times_min, ys, mask):
            if not m:
                continue
            if y <= -9:
                continue

            # Channel-specific cutoffs
            if ch == "50K" and y < 50:
                continue
            if ch == "4K" and y < 10:
                continue

            ts_plot.append(t)
            ys_plot.append(y)

        if len(ts_plot) < 2:
            continue

        line, = ax.plot(ts_plot, ys_plot, label=ch)
        legend_entries.append((ch, ys_plot, ts_plot))

    if not legend_entries:
        return "No valid data to plot", 503

    leg = ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        frameon=True,
        fontsize="small"
    )

    # Update legend text with current value + gradient
    for text, (ch, ys, ts) in zip(leg.texts, legend_entries):
        current = ys[-1]

        # Gradient over last 30 seconds
        grad_text = ""
        t_now = ts[-1]
        for i in range(len(ts) - 1, -1, -1):
            if (t_now - ts[i]) * 60 >= 30:
                dt_min = t_now - ts[i]
                grad = (ys[-1] - ys[i]) / dt_min * 1000.0  # mK/min
                grad_text = f"\n{grad:+.1f}mK/min"
                break

        text.set_text(f"{ch} {current:.3f}K{grad_text}")

    fig.tight_layout()
    buf = io.BytesIO()
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

@app.route("/api/plotly_data")
def api_plotly_data():
    update_latest_plot_data()
    if "latest_plot_snapshot" not in globals():
        return jsonify({})

    return jsonify(latest_plot_snapshot)

@app.route("/interactive")
def interactive():
    return render_template("interactive.html")

'''
@app.route("/interactive")
def interactive():
    # Build device → channels mapping from PLOT_MAPPING
    devices_context = {}

    for _, (dev, channels) in PLOT_MAPPING.items():
        devices_context.setdefault(dev, [])
        for ch in channels:
            if ch not in devices_context[dev]:
                devices_context[dev].append(ch)

    return render_template(
        "interactive.html",
        devices=devices_context
    )
'''

# Run server
if __name__ == "__main__":
    # run webserver on port 8083
    app.run(debug=False, host="0.0.0.0", port=8083)

