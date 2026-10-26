import threading
import time
from datetime import datetime

from sql import SQL 
from channel import Channel 

class TemperatureReadout(threading.Thread):
    def __init__(self, channels, sql: SQL, period=5.0):
        super().__init__(daemon=True)
        self.channels = channels
        self.sql = sql
        self.period = period
        self._stop = threading.Event()

    """
    def run(self):
        while not self._stop.is_set():
            timestamp = datetime.now()
            for ch in self.channels.values():
                try:
                    value = ch.read_temperature()
                except Exception as e:
                    print("[TemperatureReadoutThread] ERROR during Channel.read_temperature():", e)
                # Safety check: ignore Nones or weird values
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    print(f"[TemperatureReadoutThread] Skipping invalid value for {ch.name}: {value}")
                    continue
                self.sql.insertSCValueByName(ch.name, value, timestamp)
            # Sleep with interrupt support
            self._stop.wait(self.period)
        print("[TemperatureReadoutThread] Stopped.")
    """

    def run(self):
        while not self._stop.is_set():
            timestamp = datetime.now()
            for ch in self.channels.values():
                try:
                    value = ch.read_temperature()
                except Exception as e:
                    print("[TemperatureReadout] ERROR reading channel:", ch.name, e)
                    continue

                try:
                    value = float(value)
                except (TypeError, ValueError):
                    print(f"[TemperatureReadout] Skipping invalid value for {ch.name}: {value}")
                    continue

                try:
                    self.sql.insertSCValueByName(ch.name, value, timestamp)
                except Exception as e:
                    print(f"[TemperatureReadout] DB write failed for {ch.name}: {e}")
                    try:
                        self.sql.db.rollback()
                    except Exception:
                        print("[TemperatureReadout] Connection lost, reconnecting...")
                        try:
                            self.sql.reconnect()
                        except Exception as e2:
                            print("[TemperatureReadout] Reconnect failed:", e2)
                            break  # skip remaining channels this cycle, try again next period

            self._stop.wait(self.period)

        print("[TemperatureReadoutThread] Stopped.")


    def stop(self):
        self._stop.set()
