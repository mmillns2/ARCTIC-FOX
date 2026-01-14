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

        # strip " [K]"
        self.clean_names = {name: name.replace(" [K]", "") for name in channel_names}

        # maps clean channel name -> device
        self.device_map = {
            ch: dev
            for dev, chans in plot_data.items()
            for ch in chans.keys()
            if ch != "times"
        }

        # SCID lookup
        self.scids = {name: sql.getSCID(name) for name in channel_names}

        last = sql.lastUpdate()
        self.last_timestamp = int(last.timestamp()) if last else 0

        # working state
        self.state = copy.deepcopy(plot_data)

        # last-known values (for forward fill)
        self.last_values = {
            (dev, ch): None
            for dev, chans in plot_data.items()
            for ch in chans
            if ch != "times"
        }

    def run(self):
        print("[DBReader] Starting DB poll thread (aligned mode).")

        while True:
            try:
                timestamps = self.sql.getSCTimes(self.last_timestamp)
                if not timestamps:
                    time.sleep(self.interval)
                    continue

                # only use last timestamp
                ts = max(timestamps)

                rows = self.sql.getSCValues(list(self.scids.values()), ts)
                if not rows:
                    time.sleep(self.interval)
                    continue

                record = rows[0]
                t = record["time"]

                # Track which channels updated this cycle
                updated = set()

                # Read DB values
                for i, full_name in enumerate(self.channel_names):
                    clean = self.clean_names[full_name]
                    dev = self.device_map.get(clean)
                    if not dev:
                        continue

                    raw = record.get(f"value-{i+1}")
                    try:
                        val = float(raw)
                    except:
                        continue

                    if val < -9:
                        continue

                    self.last_values[(dev, clean)] = val
                    updated.add((dev, clean))

                # Append aligned values (forward fill)
                for dev, chans in self.state.items():
                    if dev == "times":
                        continue

                    self.state[dev]["times"].append(t)

                    for ch in chans:
                        if ch == "times":
                            continue

                        val = self.last_values[(dev, ch)]
                        if val is not None:
                            self.state[dev][ch].append(val)
                        else:
                            # still no data yet -> repeat or skip
                            if self.state[dev][ch]:
                                self.state[dev][ch].append(self.state[dev][ch][-1])

                # Emit snapshot
                self.plot_queue.put(copy.deepcopy(self.state))
                self.last_timestamp = t

            except Exception as e:
                self.sql.db.rollback()
                print("[DBReader] ERROR:", e)

            time.sleep(self.interval)

