from controller_server import DeviceControllerServer
from flask import Flask, render_template, request, jsonify, Response

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
    # If later add Lakeshore224 mapping, add here
    return {}

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

# Run server
if __name__ == "__main__":
    # run webserver on port 8083
    app.run(debug=False, host="0.0.0.0", port=8083)
