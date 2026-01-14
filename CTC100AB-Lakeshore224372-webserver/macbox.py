from controller_client import DeviceControllerClient
from hardware_readout import HardwareTemperatureReader
from sql import SQL
from device import connect_devices

HOST = "0.0.0.0"
PORT = 8084

if __name__ == "__main__":
    # load devices and create controller
    devices = connect_devices()
    print("Detected devices:", list(devices.keys()))
    controller = DeviceControllerClient(devices, HOST, PORT)

    # create sql database instance
    sql = SQL(debug=False, options=["localhost", "axion_writer", 8082, "axion_db"])

    # create hardware reader
    temp_reader = HardwareTemperatureReader(devices, sql)

    # start controller thread
    controller.start()

    # start the temperature readout thread
    temp_reader.start()

    # keep main thread alive
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\nStopping programme.")
        controller.stop()
        controller.join()

