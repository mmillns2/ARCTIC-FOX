import yaml
from channel import Channel
from backends import *
from pid_worker import PIDWorker

def load_config(path, devices, hwio):
    with open(path) as f:
        cfg = yaml.safe_load(f)

    channels = {}

    for name, c in cfg["channels"].items():
        backend_type = c["backend"]

        if backend_type == "manual":
            if "temperature" in c:
                dev = devices[c["temperature"]["device"]]
                read_fn = lambda d=dev, ch=c["temperature"]["channel"]: \
                    hwio.call(d.get_temperature, ch)
            elif "voltage" in c:
                dev = devices[c["voltage"]["device"]]
                read_fn = lambda d=dev, ch=c["voltage"]["channel"]: \
                    hwio.call(d.get_voltage, ch)

            act_dev = devices[c["actuator"]["device"]]
            act_fn = lambda v, d=act_dev, ch=c["actuator"]["channel"]: \
                hwio.call(d.set_voltage, ch, v)

            backend = ManualBackend(read_fn, act_fn)

        elif backend_type == "software_pid":
            dev = devices[c["temperature"]["device"]]
            read_fn = lambda d=dev, ch=c["temperature"]["channel"]: \
                hwio.call(d.get_temperature, ch)

            act_dev = devices[c["actuator"]["device"]]
            write_fn = lambda v, d=act_dev, ch=c["actuator"]["channel"]: \
                hwio.call(d.set_voltage, ch, v)

            pid = PIDWorker(name, hwio, read_fn, write_fn, **c["pid"])
            backend = SoftwarePIDBackend(read_fn, pid)

        elif backend_type == "hardware_pid":
            dev = devices[c["temperature"]["device"]]
            read_fn = lambda d=dev, ch=c["temperature"]["channel"]: \
                hwio.call(d.get_temperature, ch)

            act_dev = devices[c["actuator"]["device"]]
            sp_fn = lambda v, d=act_dev, ch=c["actuator"]["channel"]: \
                hwio.call(d.set_setpoint, ch, v)
            backend = HardwarePIDBackend(read_fn, sp_fn)

        elif backend_type == "readout":
            dev = devices[c["temperature"]["device"]]
            read_fn = lambda d=dev, ch=c["temperature"]["channel"]: \
                hwio.call(d.get_temperature, ch)

            backend = ReadoutBackend(read_fn)

        elif backend_type == "readout_R":
            dev = devices[c["resistance"]["device"]]
            read_fn = lambda d=dev, ch=c["resistance"]["channel"]: \
                hwio.call(d.get_resistance, ch)
            
            backend = ReadoutBackend(read_fn)
                
        elif backend_type == "readout_V":
            dev = devices[c["voltage"]["device"]]
            read_fn = lambda d=dev, ch=c["voltage"]["channel"]: \
                hwio.call(d.get_voltage, ch)

            backend = ReadoutBackend(read_fn)

        if "webserver" in c:
            can_control = True
            if "controller" in c["webserver"]:
                can_control = bool(c["webserver"]["controller"])

            units = ""
            if "units" in c["webserver"]:
                units = str(c["webserver"]["units"])

            display = True
            if "display" in c["webserver"]:
                display = bool(c["webserver"]["display"])

            algorithm = None                          
            if "algorithm" in c["webserver"]:             
                algorithm = str(c["webserver"]["algorithm"])

            channels[name] = Channel(name, backend, can_control, units, display, algorithm)
        else:
            channels[name] = Channel(name, backend)

    print('Channels connected:')
    for name, ch in channels.items():
        print(name, end=", ")
    print('')

    return channels

def load_settings(path):
    '''
    Read the required ports and database sections of the config file.
    '''
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}

    required = {
        "ports":    ["webserver", "controller", "database"],
        "database": ["host", "user", "name"],
    }

    missing = []
    for section, keys in required.items():
        if not isinstance(cfg.get(section), dict):
            missing.append(f"'{section}:' section")
            continue
        for key in keys:
            if cfg[section].get(key) is None:
                missing.append(f"{section}.{key}")

    if missing:
        raise ValueError(f"Config file {path} is missing: {', '.join(missing)}")

    p, d = cfg["ports"], cfg["database"]

    ports = {k: int(p[k]) for k in required["ports"]}
    database = {k: str(d[k]) for k in required["database"]}

    return ports, database
