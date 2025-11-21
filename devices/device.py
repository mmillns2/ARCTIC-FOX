import serial.tools.list_ports
from threading import RLock

from devices.CTC100 import CTC100Device
from devices.lakeshore224device import LakeShore224Device
from devices.lakeshore372device import LakeShore372Device

# Global re-entrant lock used to synchronize access to serial devices
device_lock = RLock()

def connect_devices():
    """Scan serial ports and construct device wrappers. Returns dict of name->device.

    Each returned device is expected to expose the same methods used elsewhere
    (get_temperature, write_setpoint, set_still_voltage, etc.).
    """
    ports = serial.tools.list_ports.comports()

    ctc100A = None
    ctc100B = None
    model224 = None
    model372 = None

    for p in ports:
        desc = (p.description or "").lower()
        sn = (p.serial_number or "")
        if 'ft230x' in desc:
            # match the serial numbers you used previously
            if 'dk0cdlqp' in sn:
                ctc100B = CTC100Device(address=p.device, name='CTC100B')
            elif 'dk0cdkfb' in sn:
                ctc100A = CTC100Device(address=p.device, name='CTC100A')
        elif '224' in desc:
            model224 = LakeShore224Device(port=p.device, name='Lakeshore224')
        elif '372' in desc:
            model372 = LakeShore372Device(port=p.device, name='Lakeshore372')

    connected = {
    'CTC100A': ctc100A,
    'CTC100B': ctc100B,
    'Lakeshore224': model224,
    'Lakeshore372': model372,
    }

    # Filter out None entries
    return {k: v for k, v in connected.items() if v is not None}
