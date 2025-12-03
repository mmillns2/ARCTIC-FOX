from controller_client import DeviceControllerClient
from device import connect_devices

HOST = "0.0.0.0"
PORT = 8084

if __name__ == "__main__":
    # load devices and create controller
    devices = connect_devices()
    print("Detected devices:", list(devices.keys()))
    controller = DeviceControllerClient(devices, HOST, PORT)

    # start controller thread
    controller.start()

    # start temperature readout thread

    # keep main thread alive
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\nStopping programme.")
        controller.stop()
        controller.join()

