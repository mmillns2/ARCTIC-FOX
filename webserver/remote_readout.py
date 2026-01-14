import threading
import time
import copy
import datetime
import queue

plot_data = {
    "CTC100A": {"times": [], "4switchA": [], "4pumpA": [], "3switchA": [], "3pumpA": []},
    "CTC100B": {"times": [], "4switchB": [], "4pumpB": [], "3switchB": [], "3pumpB": []},
    "Lakeshore372": {"times": [], "MC": [], "Still": []},
    "Lakeshore224": {"times": [], "4HePotA": [], "3HePotA": [], "4HePotB": [], "3HePotB": [], "Condenser": [], "50K": [], "4K": []}
}

channel_names = [
    "4switchA [K]",
    "4pumpA [K]",
    "3switchA [K]",
    "3pumpA [K]",
    "4switchB [K]",
    "4pumpB [K]",
    "3switchB [K]",
    "3pumpB [K]",
    "4HePotA [K]",
    "3HePotA [K]",
    "4HePotB [K]",
    "3HePotB [K]",
    "Condenser [K]",
    "50K [K]",
    "4K [K]",
    "MC [K]",
    "Still [K]"
]

class DBReader(threading.Thread):
    def __init__(self, sql, plot_queue, channel_names=channel_names, interval=2.0):
        super().__init__(daemon=True)

        self.sql = sql
        self.channel_names = channel_names
        self.plot_queue = plot_queue
        self.interval = interval

        # strip " [K]" suffix
        self.clean_names = {name: name.replace(" [K]", "") for name in channel_names}

        # maps clean channel name -> device
        self.device_map = {
            ch: dev
            for dev, chans in plot_data.items()
            for ch in chans.keys()
            if ch != "times"
        }

        # SCID lookup for full names
        self.scids = {name: sql.getSCID(name) for name in channel_names}

        last = sql.lastUpdate()
        self.last_timestamp = int(last.timestamp()) - 1 if last else 0

        # working internal state (deepcopy)
        self.state = copy.deepcopy(plot_data)

    def run(self):
        print("[DBReader] Starting DB poll thread.")

        while True:
            try:
                timestamps = self.sql.getSCTimes(self.last_timestamp)

                if not timestamps:
                    # No new rows, sleep and continue
                    time.sleep(self.interval)
                    continue

                for ts in sorted(timestamps):
                    rows = self.sql.getSCValues(list(self.scids.values()), ts)
                    if not rows:
                        continue

                    record = rows[0]
                    t = record["time"]

                    updated_devices = set()

                    for i, full_name in enumerate(self.channel_names):

                        clean = self.clean_names[full_name]
                        dev = self.device_map.get(clean)
                        if not dev:
                            continue

                        raw = record[f"value-{i+1}"]

                        try:
                            val = float(raw)
                        except:
                            continue

                        if val < -9:
                            continue

                        self.state[dev][clean].append(val)
                        updated_devices.add(dev)

                    for dev in updated_devices:
                        self.state[dev]["times"].append(t)

                    #print("plot_data snapshot:", self.state)

                    # push snapshot
                    self.plot_queue.put(copy.deepcopy(self.state))

                    self.last_timestamp = t

            except Exception as e:
                self.sql.db.rollback()
                print("[DBReader] ERROR:", e)

            time.sleep(self.interval)

