class Channel:
    '''
    Logical control point.
    '''
    def __init__(self, name, backend, can_control=None, units=None, display=None, algorithm=None):
        self.name = name
        self.backend = backend
        self.can_control = can_control
        self.units = units
        self.display = display
        self.algorithm = algorithm
        self.last_temperature = None
        self.last_output = None

    def read_temperature(self):
        t = self.backend.read()
        if t is not None:
            self.last_temperature = t
        return self.last_temperature

    def set_setpoint(self, value):
        self.backend.set_setpoint(value)
        self.last_output = value

    def set_manual(self, value):
        self.backend.set_manual(value)
        self.last_output = value

    def off(self):
        self.backend.off()
        self.last_output = 0.0
