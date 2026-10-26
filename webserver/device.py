import serial.tools.list_ports
from threading import RLock

#from CTC100 import CTC100Device
#from lakeshore224device import LakeShore224Device
#from lakeshore372device import LakeShore372Device

from lakeshore218device import LakeShore218Device
from lakeshore336device import LakeShore336Device
from lakeshore350device import LakeShore350Device
from lakeshore372device import LakeShore372Device
from MX103QP import MX103QP
from GPDX303S import GPDX303S
from diodedevice import OllieDiodeDevice
from N5745A import N5745A 

# Global re-entrant lock used to synchronize access to serial devices
device_lock = RLock()

import serial.tools.list_ports
from collections import defaultdict


def connect_devices():
    """Scan serial ports and construct device wrappers. Returns dict of name->device.

    Each returned device is expected to expose the same methods used elsewhere
    (get_temperature, write_setpoint, set_still_voltage, etc.).
    """
    devices = serial.tools.list_ports.comports()

    ctc100A = None
    ctc100B = None
    model224 = None
    model372 = None

    model218 = None
    model336 = None
    model350 = None

    heater_ps = None
    switch_psA = None   # H1
    switch_psB = None   # H2

    olliebox = None

    magnet_ps = None

    for device in devices:
        print(device.description)
        if 'FT230X' in device.description:
            # match the serial numbers used previously
            if 'DK0CDLQP' in device.serial_number:
                ctc100B = CTC100Device(address=device.device, name='CTC100B')
            elif 'DK0CDKFB' in device.serial_number:
                ctc100A = CTC100Device(address=device.device, name='CTC100A')

        elif '224' in device.description:
            model224 = LakeShore224Device(port=device.device, name='Lakeshore224')

        elif '372' in device.description:
            model372 = LakeShore372Device(port=device.device, name='Lakeshore372')

        elif 'USB2.0-Ser!' in device.description:
            model218 = LakeShore218Device(port=device.device, name='Lakeshore218')

        elif '336' in device.description:
            model336 = LakeShore336Device(port=device.device, name='Lakeshore336')

        elif '350' in device.description:
            model350 = LakeShore350Device(port=device.device, name='Lakeshore350')

        elif 'MX Series PSU' in device.description:
            heater_ps = MX103QP(port=device.device, name='MX103QP')

        elif 'FT232R' in device.description:
            if 'AQ02VYPE' in device.serial_number:
                switch_psA = GPDX303S(port=device.device, name='GPDX303SA')
            elif 'AQ02V070' in device.serial_number:
                switch_psB = GPDX303S(port=device.device, name='GPDX303SB')

        #elif 'USB2.0-Ser!' in device.description:
        #    olliebox = OllieDiodeDevice(port=device.device, name='DiodeBox')

    # N5745A is USBTMC, not a serial port -> it won't appear in comports().
    # Discover it separately via pyvisa.
    try:
        magnet_ps = N5745A(name='N5745A')
        print("Connected N5745A (USBTMC)")
    except Exception as e:
        print(f"N5745A not found: {e}")
        magnet_ps = None

    connected = {
        'CTC100A': ctc100A,
        'CTC100B': ctc100B,
        'Lakeshore224': model224,
        'Lakeshore372': model372,
        'Lakeshore218': model218,
        'Lakeshore336': model336,
        'Lakeshore350': model350,
        'MX103QP': heater_ps,
        'GPDX303SA': switch_psA,
        'GPDX303SB': switch_psB,
        'DiodeBox' : olliebox,
        'N5745A' : magnet_ps,
    }

    # Filter out None entries
    return {k: v for k, v in connected.items() if v is not None}
