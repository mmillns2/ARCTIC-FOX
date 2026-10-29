import threading
import time
import copy
import queue
from collections import deque

class DBReader(threading.Thread):

    def __init__(self, sql, plot_queue, channels, interval=2.0, max_points=200_000):
        super().__init__(daemon=True)

        self.sql = sql
        self.channels = channels          # exact DB names (with [K])
        self.plot_queue = plot_queue
        self.interval = interval

        # SCID lookup
        # Ensure channels is a list
        if isinstance(channels, str):
            channels = [channels]

        self.scids = {ch: sql.getSCID(ch) for ch in channels}

        # last timestamp
        last = sql.lastUpdate()
        self.last_timestamp = int(last.timestamp()) if last else 0

        # plotting state
        self.state = {
            "times": deque(maxlen=max_points),
            **{ch: deque(maxlen=max_points) for ch in channels}
        }

        # last values for forward fill
        self.last_values = {ch: None for ch in channels}

    def run(self):

        print("[DBReader] Starting DB poll thread.")

        while True:
            try:
                timestamps = self.sql.getSCTimes(self.last_timestamp)
                if not timestamps:
                    time.sleep(self.interval)
                    continue

                ts = max(timestamps)

                scid_list = list(self.scids.values())
                rows = self.sql.getSCValues(scid_list, ts)
                if not rows:
                    time.sleep(self.interval)
                    continue

                record = rows[0]
                t = record["time"]

                # build scid -> value using positional index (value-1 = scid_list[0], etc.)
                scid_to_value = {}
                for i, scid in enumerate(scid_list):
                    raw = record.get(f"value-{i+1}")
                    try:
                        scid_to_value[scid] = float(raw)
                    except (TypeError, ValueError):
                        scid_to_value[scid] = None

                for ch in self.channels:
                    val = scid_to_value.get(self.scids[ch])
                    if val is None or val < -9:
                        continue
                    self.last_values[ch] = val

                # append aligned values
                self.state["times"].append(t)

                for ch in self.channels:

                    val = self.last_values[ch]

                    if val is not None:
                        self.state[ch].append(val)
                    else:
                        if self.state[ch]:
                            self.state[ch].append(self.state[ch][-1])

                # emit snapshot
                snapshot = {k: list(v) for k, v in self.state.items()}
                try:
                    self.plot_queue.put_nowait(snapshot)
                except queue.Full:
                    try:
                        self.plot_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.plot_queue.put_nowait(snapshot)

                self.last_timestamp = t

                """
                except Exception as e:
                    self.sql.db.rollback()
                    print("[DBReader] ERROR:", e)
                """

            except Exception as e:
                print("[DBReader] ERROR:", e)
                try:
                    self.sql.db.rollback()
                except Exception:
                    print("[DBReader] Connection lost, reconnecting...")
                    try:
                        self.sql.reconnect()
                        # Re-fetch SCIDs in case DB was rebuilt
                        self.scids = {ch: self.sql.getSCID(ch) for ch in self.channels}
                    except Exception as e2:
                        print("[DBReader] Reconnect failed:", e2)

            time.sleep(self.interval)
