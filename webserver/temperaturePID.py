from threading import Thread, Event, RLock
from simple_pid import PID
import time

class TemperaturePID(Thread):
    '''
    Runs a temperature PID in a background thread.
    '''
    def __init__(self, setpoint: float, hardware_lock: RLock, stop_event: Event, power_supply, power_supply_ch, temp_reader, temp_reader_ch):
        super().__init__(daemon=True)

        self.setpoint = setpoint

        self.hardware_lock = hardware_lock
        self.stop_event = stop_event

        self.power_supply = power_supply
        self.power_supply_ch = power_supply_ch

        self.temp_reader = temp_reader
        self.temp_reader_ch = temp_reader_ch

        self.pid = PID(1, 0.1, 0.05, setpoint=self.setpoint)

    def run(self):
        '''
        PID hot loop. Hot loop runs until stop_event is set.
        '''
        try:
            # Get current temperature (ie from lakeshore)
            temperature = self.temp_reader.get_temperature(self.temp_reader_ch)

            while not self.stop_event.is_set():

                # Compute new output from the PID according to the systems current value
                voltage = self.pid(temperature)

                # Feed the PID output to the system and get its current value
                temperature = self.power_supply.set_voltage(self.power_supply_ch, voltage)
                
        except Exception as e:
            print(f"Fatal error in TemperaturePID: {e}")
