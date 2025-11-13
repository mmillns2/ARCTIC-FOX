from cooldown_loop_dilution_v2 import switch_on, switch_off, heater_off, heater_on
from CTC100 import CTC100Device
from lakeshore224device import LakeShore224Device
from lakeshore372device import LakeShore372Device
import serial
import time
import serial.tools.list_ports

def connect_devices():
    devices = serial.tools.list_ports.comports()

    ctc100A = None
    ctc100B = None
    model224 = None
    model372 = None

    for device in devices:
        if 'FT230X' in device.description:
            if 'DK0CDLQP' in device.serial_number:
                ctc100B = CTC100Device(address=device.device, name='CTC100B')
            elif 'DK0CDKFB' in device.serial_number:
                ctc100A = CTC100Device(address=device.device, name='CTC100A')
        elif '224' in device.description:
            model224 = LakeShore224Device(port=device.device, name='LakeshoreModel224')
        elif '372' in device.description:
            model372 = LakeShore372Device(port=device.device, name='LakeshoreModel372')

    connected = {
        "CTC100A": ctc100A,
        "CTC100B": ctc100B,
        "LakeshoreModel224": model224,
        "LakeshoreModel372": model372
    }

    # Remove None entries
    return {k: v for k, v in connected.items() if v is not None}

def main():
    devices = connect_devices()

    # HEAT SWITCHES test
    #time.sleep(20)
    devices['CTC100A'].set_aio_iotype('AIO3', 'Set Out')
    time.sleep(10)
    switch_on(devices['CTC100A'], 'AIO3')
    time.sleep(10)
    switch_off(devices['CTC100A'], 'AIO3')

    # HEATERS test
    #time.sleep(20)
    #heater_on(devices['CTC100A'], '4puheat')
    #time.sleep(20)
    #heater_off(devices['CTC100A'], '4puheat')


if __name__ == "__main__":
    main()