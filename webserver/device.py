import serial.tools.list_ports
from threading import RLock

from CTC100 import CTC100Device
from lakeshore224device import LakeShore224Device
from lakeshore372device import LakeShore372Device

from lakeshore218device import LakeShore218Device
from lakeshore336device import LakeShore336Device
from lakeshore350device import LakeShore350Device
from MX103QP import MX103QP
from GPDX303S import GPDX303S

# Global re-entrant lock used to synchronize access to serial devices
device_lock = RLock()

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
    switch_ps = None

    for device in devices:
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

        elif '218' in device.description:
            model372 = LakeShore218Device(port=device.device, name='Lakeshore218')

        elif '336' in device.description:
            model372 = LakeShore336Device(port=device.device, name='Lakeshore336')

        elif '350' in device.description:
            model372 = LakeShore350Device(port=device.device, name='Lakeshore350')

        elif 'MX103QP' in device.description:
            heater_ps = MX103QP(port=device.device, name='MX103QP')

        elif 'GPDX303S' in device.description:
            switch_ps = GPDX303S(port=device.device, name='GPDX303S')


    connected = {
        'CTC100A': ctc100A,
        'CTC100B': ctc100B,
        'Lakeshore224': model224,
        'Lakeshore372': model372,
        'Lakeshore218': model218,
        'Lakeshore336': model336,
        'Lakeshore350': model350,
        'MX103QP': heater_ps,
        'GPDX303S': switch_ps,
    }

    # Filter out None entries
    return {k: v for k, v in connected.items() if v is not None}

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
        
        elif dev_name in "Lakeshore218":
            return {
                "4puheatA": "heater",
                "3puheatA": "heater",
                "4puheatB": "heater",
                "3puheatB": "heater",
                "4swheatA": "switch",
                "3swheatA": "switch",
                "4swheatB": "switch",
                "3swheatB": "switch",
            }

        elif dev_name in "Lakeshore350":
            return {"still": "still_heater"}

        return {}
