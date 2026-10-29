from remote_controller import RemoteController
from remote_readout import DBReader
from flask import Flask, render_template, request, jsonify
from sql import SQL
from config_loader import load_settings

import queue
from algorithm import Cycle, AlgorithmConfig

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


if len(sys.argv) != 2:
    print("Usage: mu2edaq2.py <config.yaml>")
    sys.exit(1)

config_path = sys.argv[1]

ports, database = load_settings(config_path)

LAST_VALUES = {}
LAST_STATES = {}

HARDWARE_CONNECTED = False

app = Flask(__name__, template_folder="templates")

controller = RemoteController("0.0.0.0", ports["controller"])
try:
    channel_info = controller.get_channels()
    HARDWARE_CONNECTED = True
except Exception:
    channel_info = {}
    HARDWARE_CONNECTED = False

channels = channel_info.keys()

def compute_algo_maps(channel_info):
    algo_channels = {}
    backend_types = {}
    for ch, info in channel_info.items():
        backend_types[ch] = info[0]
        role = info[4] if len(info) > 4 else None   # tolerant of old backends
        if role:
            algo_channels[role] = ch
    return algo_channels, backend_types

algo_channels, backend_types = compute_algo_maps(channel_info)

algorithm_config = AlgorithmConfig()
cycle_thread = Cycle(controller, algorithm_config, LAST_VALUES, LAST_STATES,
                     algo_channels, backend_types)
cycle_thread.start()

for ch in channels:
    LAST_VALUES[ch] = None
    LAST_STATES[ch] = "off"

@app.route("/")
def root():
    return """
    <h2>ARCTIC FOX interface</h2>
    <p><a href="/interactive">Display (interactive plot)</a></p>
    <p><a href="/controller">Controller (control panel)</a></p>
    <p><a href="/algorithm">Algorithm (config panel)</a></p>
    """

# Algorithm
@app.route("/algorithm")
def algorithm_page():
    role_backends = {role: backend_types.get(ch) for role, ch in algo_channels.items()}
    return render_template("algorithm.html", defaults=algorithm_config,
                           role_backends=role_backends)

@app.route("/api/algorithm/config", methods=["POST"])
def set_algorithm_config():

    data = request.json
    side = data["side"]
    key = data["key"]
    value = data["value"]

    side_cfg = getattr(algorithm_config, side)
    setattr(side_cfg, key, value)

    return jsonify({"status": "ok"})

@app.route("/api/algorithm/status")
def algorithm_status():
    return jsonify(cycle_thread.get_status())

@app.route("/api/algorithm/start", methods=["POST"])
def start_algorithm():
    cycle_thread.cmd_start()
    return jsonify({"status": "started"})

@app.route("/api/algorithm/stop", methods=["POST"])
def stop_algorithm():
    cycle_thread.cmd_stop()
    return jsonify({"status": "stopped"})

@app.route("/api/algorithm/initial_precool", methods=["POST"])
def algorithm_initial_precool():
    data = request.json
    value = float(data["value"])
    cycle_thread.cmd_initial_precool(value)
    return jsonify({"status": "ok"})

@app.route("/api/algorithm/pre_cycle_cool", methods=["POST"])
def algorithm_pre_cool_cycle():
    data = request.json
    value = float(data["value"])
    cycle_thread.cmd_pre_cycle_cool(value)
    return jsonify({"status": "ok"})


# Controller UI
# filter only channels that should appear in controller
controller_channels = [ch for ch,info in channel_info.items() if info[1]]

@app.route("/controller")
def controller_page():

    return render_template(
        "controller.html",
        channels=controller_channels,
        channel_info=channel_info,
        last_values=LAST_VALUES,
        last_states=LAST_STATES,
        hardware_connected=HARDWARE_CONNECTED
    )

@app.route("/api/controller_state")
def api_controller_state():

    return jsonify({
        "values": LAST_VALUES,
        "states": LAST_STATES
    })

@app.route("/api/set_value", methods=["POST"])
def api_set_value():

    data = request.json
    ch = data["channel"]
    value = float(data["value"])

    backend_type = channel_info[ch][0]

    if backend_type == "software_pid" or backend_type == "hardware_pid":
        controller.set_setpoint(ch, value)

    elif backend_type == "manual":
        controller.set_manual(ch, value)

    else:
        return jsonify({"status":"error","msg":"unsupported backend"}),400

    LAST_VALUES[ch] = value
    LAST_STATES[ch] = "on"

    return jsonify({"status":"ok"})

@app.route("/api/turn_off", methods=["POST"])
def api_turn_off():

    data = request.json
    ch = data["channel"]

    controller.off(ch)

    LAST_VALUES[ch] = None
    LAST_STATES[ch] = "off"

    return jsonify({"status":"ok"})


# Plotting
sql = SQL(debug=False, options=[database["host"], database["user"],
                                ports["database"], database["name"]])

plot_queue = queue.Queue(maxsize=5)

# filter only channels that should be displayed
display_channels = [ch for ch,info in channel_info.items() if info[3]]

db_reader = DBReader(sql, plot_queue, display_channels)
db_reader.start()

latest_plot_snapshot = {}


def update_latest_plot_data():

    global latest_plot_snapshot

    try:
        while True:
            snapshot = plot_queue.get_nowait()
            latest_plot_snapshot = snapshot
    except queue.Empty:
        pass


MAX_DISPLAY_POINTS = 5000

@app.route("/api/plotly_data")
def api_plotly_data():
    update_latest_plot_data()
    snap = latest_plot_snapshot
    n = len(snap.get("times", []))
    if n <= MAX_DISPLAY_POINTS:
        return jsonify(snap)

    step = n // MAX_DISPLAY_POINTS
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)          # always include the latest point
    return jsonify({k: [v[i] for i in idx] for k, v in snap.items()})

@app.route("/interactive")
def interactive():
    return render_template("interactive.html")


def do_reconnect():
    global channel_info, channels, controller_channels, display_channels
    global db_reader, HARDWARE_CONNECTED
    global algo_channels, backend_types

    channel_info = controller.get_channels()  # raises on failure
    HARDWARE_CONNECTED = True
    channels = channel_info.keys()

    for ch in channels:
        if ch not in LAST_VALUES:
            LAST_VALUES[ch] = None
        if ch not in LAST_STATES:
            LAST_STATES[ch] = "off"

    controller_channels = [ch for ch, info in channel_info.items() if info[1]]
    display_channels = [ch for ch, info in channel_info.items() if info[3]]

    if not db_reader.is_alive():
        db_reader = DBReader(sql, plot_queue, display_channels)
        db_reader.start()

    algo_channels, backend_types = compute_algo_maps(channel_info)
    cycle_thread.set_channel_map(algo_channels, backend_types)


@app.route("/api/reconnect", methods=["POST"])
def api_reconnect():
    try:
        do_reconnect()
        return jsonify({"status": "ok"})
    except Exception as e:
        HARDWARE_CONNECTED = False
        return jsonify({"status": "error", "msg": str(e)}), 503


@app.route("/api/hardware_status")
def api_hardware_status():
    global HARDWARE_CONNECTED
    try:
        controller.ping()
        if not HARDWARE_CONNECTED:
            do_reconnect()
        HARDWARE_CONNECTED = True
    except Exception:
        HARDWARE_CONNECTED = False
    return jsonify({"connected": HARDWARE_CONNECTED})


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=ports["webserver"])
