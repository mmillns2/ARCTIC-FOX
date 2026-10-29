import sys
import signal
import time
from sql import SQL

from hardwareio import HardwareIO
from config_loader import load_config, load_settings
from temperature_readout import TemperatureReadout
from controller import Controller

from lakeshore350device import LakeShore350Device
from MX103QP import MX103QP

from device import connect_devices


def main():
    if len(sys.argv) != 2:
        print("Usage: cryo <config.yaml>")
        sys.exit(1)

    config_path = sys.argv[1]

    # Instantiate physical devices (edit as hardware changes)
    devices = connect_devices()

    # Core infrastructure
    hwio = HardwareIO()

    channels = load_config(config_path, devices, hwio)

    ports, database = load_settings(config_path)

    sql = SQL(debug=False, options=[database["host"], database["user"],
                                    ports["database"], database["name"]])

    # Threads
    temp_readout = TemperatureReadout(
        channels=channels,
        sql=sql,
        period=2.0
    )

    controller = Controller(
        channels=channels,
        host="0.0.0.0",
        port=8084
    )

    # Startup
    print("Starting cryo backend...")
    temp_readout.start()
    controller.start()

    def shutdown(signum, frame):
        print("\nShutting down cryo backend...")
        temp_readout.stop()

        for ch in channels.values():
            try:
                ch.off()
            except Exception:
                pass

        time.sleep(0.5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Block forever
    while True:
        #print("tick")
        time.sleep(1)


if __name__ == "__main__":
    main()
