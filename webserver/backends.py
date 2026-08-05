class ManualBackend:
    '''
    Manual actuator (switches, still, heaters without PID)
    '''
    def __init__(self, temp_reader=None, actuator=None):
        self.temp_reader = temp_reader
        self.actuator = actuator
        self.name = "manual"

    def read(self):
        return self.temp_reader() if self.temp_reader else None

    def set_manual(self, value):
        self.actuator(value)

    def set_setpoint(self, value):
        raise RuntimeError("Manual backend has no setpoint")

    def off(self):
        self.actuator(0.0)


class SoftwarePIDBackend:
    '''
    Software PID loop (pumps)
    '''
    def __init__(self, temp_reader, pid_worker):
        self.pid = pid_worker
        self.temp_reader = temp_reader
        self.name = "software_pid"

        # Start thread once
        self.pid.start()

    def read(self):
        return self.temp_reader()

    def set_setpoint(self, value):
        self.pid.set_setpoint(value)
        self.pid.enable()

    def set_manual(self, value):
        raise RuntimeError("PID backend does not support manual mode")

    def off(self):
        self.pid.disable()
        print("[SoftwarePIDBackend] off")

    def shutdown(self):
        self.pid.shutdown()
        print("[SoftwarePIDBackend] shutdown")


class HardwarePIDBackend:
    '''
    Hardware PID (CTC100, LS336, etc.)
    '''
    def __init__(self, temp_reader, setpoint_writer):
        self.read_temp = temp_reader
        self.write_setpoint = setpoint_writer
        self.name = "hardware_pid"

    def read(self):
        return self.read_temp()

    def set_setpoint(self, value):
        self.write_setpoint(value)

    def set_manual(self, value):
        raise RuntimeError("Hardware PID backend has no manual mode")

    def off(self):
        self.write_setpoint(0.0)

class ReadoutBackend:
    '''
    Readout only with no actuator (Diodes, ...)
    '''
    def __init__(self, temp_reader):
        self.read_temp = temp_reader
        self.name = "readout"

    def read(self):
        return self.read_temp()

    def set_setpoint(self, value):
        raise RuntimeError("Readout backend does not support manual mode")

    def set_manual(self, value):
        raise RuntimeError("Readout backend has no manual mode")

    def off(self):
        pass
