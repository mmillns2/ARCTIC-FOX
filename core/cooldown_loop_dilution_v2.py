import sys
import os
import time
from threading import Thread, Lock
import datetime
import serial
import serial.tools.list_ports
import numpy as np
import itertools
from devices.CTC100 import CTC100Device
from devices.lakeshore224device import LakeShore224Device
from devices.lakeshore372device import LakeShore372Device
try:
    from devices.lakeshore.model_224 import Model224
    from devices.lakeshore.model_372 import Model372
except ImportError:
    # If the lakeshore package is not installed, define None
    Model224 = None
    Model372 = None
import h5py



"""


***Description of the readout electronics:***
    - 2 CTC1000 (A and B), responsible for the management and readout of one 7He system each. 
      The channels for both are:
        In1 = 4He switch thermometer
        In2 = 3He switch thermometer
        In3 = 4He pump thermometer
        In4 = 3He pump thermometer
        Out1 =  4He pump heater
        Out2 = 3He pump heater
        AIO1 = 4He switch heater
        AIO2 = 3He switch heater
    
    - 1 Lakeshore 224, responsible for the readout of 3 thermometers:
        D2 = 40K plate
        D3 = 4K plate (2 wires) --> should be on the mainplate
        D4 = 4K plate (4 wires) --> should be on the fridge plate
        
    - 1 Lakeshore 372, responsible for the readout of 8 thermometers and the still heater:
        1 = 3He head  (bottom connector)
        2 = 4He head  (bottom connector) 
        3 = 3He head  (top connector)
        4 = 4He head  (top connector)
        5 = Still
        6 = Mixing Chamber
        7 = Condenser 
        9 = Mixing Chamber (added)
        

    

"""

### For initialisation, use an IPython terminal to check the comports and hardcode them here ###

    # if '350' in device.description:
        # model350 = LakeShore350Device(com_port=device.device, name = 'LakeshoreModel350')

# ctc100A = SimulatedCTC100Device(port = 'A', name  = 'ctc100A')
# ctc100B = SimulatedCTC100Device(port='B', name='ctc100B')
# model224 = SimulatedLakeShore224Device(port = 'C', name = 'LakeshoreModel224')
# model350 = SimulatedLakeShore372Device(port = 'D', name = 'LakeshoreModel350')


class Data_Acquisition(Thread):
    def __init__(self, data, filename, lock, start_aq=True):
        self.lock = lock
        self.data_buffer = data
        self.max_buffer = CHUNK
        self.start_acquisition = start_aq
        self.filename = filename
        super().__init__()

    def run(self):
        start_time = datetime.datetime.now().timestamp()
        with self.lock:
            
            current_time = datetime.datetime.now().timestamp() - start_time
            self.data_buffer['time'].append(current_time)
            if len(self.data_buffer['time']) > self.max_buffer:
                with h5py.File(self.filename, 'a') as database:
                    database['Time'][0:] = self.data_buffer['time']
                self.data_buffer['time'] = []

            for device in devices_list:
                if device is model372:
                    for channel in device.input_channels:
                        # if channel == '9': 
                        #     self.data_buffer[f'{device.name}/{channel}'].append(
                        #     device.get_sensor(channel))
                        #     if len(self.data_buffer[f'{device.name}/{channel}']) > self.max_buffer:
                        #         with h5py.File(self.filename, 'a') as database:
                        #             database[f'{device.name}/{channel}_sensor'][0:] = self.data_buffer[f'{device.name}/{channel}']
                        #         self.data_buffer[f'{device.name}/{channel}'] = []
                        # else:
                        self.data_buffer[f'{device.name}/{channel}'].append(device.get_temperature(channel))
                    if len(self.data_buffer[f'{device.name}/{channel}']) > self.max_buffer:
                        with h5py.File(self.filename, 'a') as database:
                            database[f'{device.name}/{channel}_temperature'][0:] = self.data_buffer[f'{device.name}/{channel}']
                        self.data_buffer[f'{device.name}/{channel}'] = []
                    for channel in device.output_channels:
                        self.data_buffer[f'{device.name}/{channel}'].append(
                            device.get_output(channel))
                        if len(self.data_buffer[f'{device.name}/{channel}']) > self.max_buffer:
                            with h5py.File(self.filename, 'a') as database:
                                database[f'{device.name}/{channel}_percentage'][0:] = self.data_buffer[f'{device.name}/{channel}']
                            self.data_buffer[f'{device.name}/{channel}'] = []

                else:
                    for channel in device.input_channels:
                        self.data_buffer[f'{device.name}/{channel}'].append(
                            device.get_temperature(channel))
                        if len(self.data_buffer[f'{device.name}/{channel}']) > self.max_buffer:
                            with h5py.File(self.filename, 'a') as database:
                                database[f'{device.name}/{channel}_temperature'][0:] = self.data_buffer[f'{device.name}/{channel}']
                            self.data_buffer[f'{device.name}/{channel}'] = []
                
        
        time.sleep(1)


        
        while self.start_acquisition:
            with self.lock:
                current_time = datetime.datetime.now().timestamp() - start_time
                self.data_buffer['time'].append(current_time)
                if len(self.data_buffer['time']) > self.max_buffer:
                    with h5py.File(self.filename, 'a') as database:
                        database['Time'].resize(
                            (database['Time'].shape[0]+len(self.data_buffer['time'])), axis=0)
                        database['Time'][-len(self.data_buffer['time']):] = self.data_buffer['time']
                    self.data_buffer['time'] = []
                for device in devices_list:
                    if device is model372:
                        for channel in device.output_channels:
                            self.data_buffer[f'{device.name}/{channel}'].append(
                                device.get_output(channel))
                            if len(self.data_buffer[f'{device.name}/{channel}']) > self.max_buffer:
                                with h5py.File(self.filename, 'a') as database:
                                    database[f'{device.name}/{channel}_percentage'].resize(
                                        (database[f'{device.name}/{channel}_percentage'].shape[0]+len(self.data_buffer[f'{device.name}/{channel}'])), axis=0)
                                    database[f'{device.name}/{channel}_percentage'][-len(
                                        self.data_buffer[f'{device.name}/{channel}']):] = self.data_buffer[f'{device.name}/{channel}']
                                self.data_buffer[f'{device.name}/{channel}'] = []

                        for channel in device.input_channels:
                            # if channel == '9':
                            #     self.data_buffer[f'{device.name}/{channel}'].append(
                            #     device.get_sensor(channel))
                            #     if len(self.data_buffer[f'{device.name}/{channel}']) > self.max_buffer:
                            #         with h5py.File(self.filename, 'a') as database:
                            #             database[f'{device.name}/{channel}_sensor'].resize(
                            #                 (database[f'{device.name}/{channel}_sensor'].shape[0]+len(self.data_buffer[f'{device.name}/{channel}'])), axis=0)
                            #             database[f'{device.name}/{channel}_sensor'][-len(
                            #                 self.data_buffer[f'{device.name}/{channel}']):] = self.data_buffer[f'{device.name}/{channel}']
                            #         self.data_buffer[f'{device.name}/{channel}'] = []       
                            # else:
                            self.data_buffer[f'{device.name}/{channel}'].append(
                                device.get_temperature(channel))
                            if len(self.data_buffer[f'{device.name}/{channel}']) > self.max_buffer:
                                with h5py.File(self.filename, 'a') as database:
                                    database[f'{device.name}/{channel}_temperature'].resize(
                                        (database[f'{device.name}/{channel}_temperature'].shape[0]+len(self.data_buffer[f'{device.name}/{channel}'])), axis=0)
                                    database[f'{device.name}/{channel}_temperature'][-len(self.data_buffer[f'{device.name}/{channel}']):] = self.data_buffer[f'{device.name}/{channel}']
                                self.data_buffer[f'{device.name}/{channel}'] = []                                               
                    else:        
                        for channel in device.input_channels:
                            self.data_buffer[f'{device.name}/{channel}'].append(
                                device.get_temperature(channel))
                            if len(self.data_buffer[f'{device.name}/{channel}']) > self.max_buffer:
                                with h5py.File(self.filename, 'a') as database:
                                    database[f'{device.name}/{channel}_temperature'].resize(
                                        (database[f'{device.name}/{channel}_temperature'].shape[0]+len(self.data_buffer[f'{device.name}/{channel}'])), axis=0)
                                    database[f'{device.name}/{channel}_temperature'][-len(
                                        self.data_buffer[f'{device.name}/{channel}']):] = self.data_buffer[f'{device.name}/{channel}']
                                self.data_buffer[f'{device.name}/{channel}'] = []
                   




            
            time.sleep(1)
            
class Cooldown_routine(Thread):
    def __init__(self, data, lock):
        self.data_buffer = data
        self.lock = lock
        
        super().__init__()
    
    def run(self):

        '''PID tuning here'''
        # with self.lock:
        #     for device in [ctc100A, ctc100B]:
        #         for channel in device.output_channels:
        #             # status = device.write(f'{channel}.value ?')
        #             status = device.get_variable(channel)
        #             if status > 0:
        #                 heater_off(device, channel)
        #         for channel in device.aio_channels[:2]:
        #             # status = device.write(f'{channel}.value ?')
        #             status = device.get_variable(channel)
        #             if status > 1:
        #                 switch_off(device, channel)
        
        # with self.lock:
        #     for system in [He7_A_channels, He7_B_channels]:
        #         heater_PID_config(system['device'],
        #                         system['He4_heater'], system['He4_pump'])
        #         heater_PID_config(system['device'],
        #                         system['He3_heater'], system['He3_pump'])
        #         heater_off(system['device'], system['He4_heater'])
        #         heater_off(system['device'], system['He3_heater'])
        # time.sleep(1)
                
                
        # with self.lock:
        #     for system in [He7_A_channels, He7_B_channels]:
        #         heater_on(system['device'], system['He4_heater'])
        #         heater_on(system['device'], system['He3_heater'])
            
        # time.sleep(100)

        '''precooling routine (not cycling but done just once)'''

        # data_copy = self.data_buffer.copy()
        # time.sleep(10)
        # self.update_list_of_temperature(data_copy)
        # for system in [He7_B_channels, He7_A_channels]:
        #     print(f"checking {system['device'].name}")
        #     while data_copy[f"LakeshoreModel372/{system['He4_head']}"][-1] > 4.0 and isfinished(data_copy['time'], data_copy[f"LakeshoreModel372/{system['He4_head']}"]):
        #         time.sleep(1)
        #         self.update_list_of_temperature(data_copy)
        #     print(f"4He Heat switch on {system['device'].name}")
        #     with self.lock:

        #         heater_off(system['device'], system['He4_heater'])
        #         switch_on(system['device'], system['He4_aio'])

        # print(f'Waiting for 10 minutes, starting at {datetime.datetime.now()}')
        # time.sleep(600)

        
        # self.update_list_of_temperature(data_copy)

        # for system in [He7_A_channels, He7_B_channels]:
        #     print(f"checking {system['device'].name} {system['He3_head']}")
        #     self.update_list_of_temperature(data_copy)
            
        #     while data_copy[f"LakeshoreModel372/{system['He3_head']}"][-1] > 1.5 and isfinished(data_copy['time'], data_copy[f"LakeshoreModel372/{system['He3_head']}"]):
        #         time.sleep(1)
        #         self.update_list_of_temperature(data_copy)
        #     print(f"Heater on {system['device'].name} {system['He3_head']}")

        #     with self.lock:

        #         heater_off(system['device'], system['He3_heater'])
        #         switch_on(system['device'], system['He3_aio'])

        
        #     self.update_list_of_temperature(data_copy)
        # print(f'sleeping 5 min starting at {datetime.datetime.now()}')
        # time.sleep(600)

        # for system in [He7_A_channels, He7_B_channels]:
        #     print('Aspettando l\'inverno')
        #     while (condition_temperature := data_copy[f"LakeshoreModel372/{system['He3_head']}"][-1] > 0.45) and (condition_stability := isfinished(data_copy['time'], data_copy[f"LakeshoreModel372/{system['He3_head']}"] )):
        #         time.sleep(2)
        #         self.update_list_of_temperature(data_copy)

        #     if not condition_temperature:
        #         print('walrus activated, sleeping 5 minutes')
        #         time.sleep(300)

                        
        # print(f'End of precooling, allowing it to stabilise, waiting 7 minute starting at {datetime.datetime.now()}')
        # time.sleep(300)
        # print('Starting flipflop cooling')
        
        list_of_systems = {'System A': [
            He7_A_channels, True], 'System_B': [He7_B_channels, False]}

        '''Cycling with load curve'''
        
        # Still_voltages = [65, 70, 30]
        # MC_setpoints = [0.07, 0.08, 0.09, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.2 ]

        # for V, setpoint, (system, status) in itertools.product(Still_voltages, MC_setpoints, list_of_systems.items()):
        #     if status:
        #         model372.set_still_voltage(V)
        #         model372.set_MC_setpoint(setpoint)
        #         print(f'Still output: {V}, Mixing Chamber setpoint: {setpoint}')
        #         status_update = self.cryo_cool(list_of_systems[system][0])
        #         list_of_systems[system][1] = status_update
        #     else:
        #         list_of_systems[system][1] = True

        # model372.set_MC_setpoint(0.04)
        # try:
        #     model372.MC_heater_turn_off()
        # except:
        #     pass

        '''setting the still and just cycle forever'''

        # model372.set_still_voltage(65)
        while True:
            for key, values in list_of_systems.items():
                system, status = values
                if status:
                    status_update = self.cryo_cool(system)
                    list_of_systems[key][1] = status_update
                else:
                    list_of_systems[key][1] = True

    def update_list_of_temperature(self, data_list):
        for key in self.data_buffer:
            data_list[key].extend(self.data_buffer[key])
        
    def cryo_cool(self, system):
        print(f"Switching off Heat switches on {system['device'].name}")
        with self.lock:

            switch_off(system['device'], system['He4_aio'])
            switch_off(system['device'], system['He3_aio'])
            
        data_copy = self.data_buffer.copy()
        print(f"checking {system['device'].name} waiting for switches to cool down below 10K")
        time.sleep(10)
        self.update_list_of_temperature(data_copy)

        while data_copy[f"{system['device'].name}/{system['He4_switch']}"][-1] > 10 or data_copy[f"{system['device'].name}/{system['He3_switch']}"][-1] > 10:
            time.sleep(2)
            self.update_list_of_temperature(data_copy)
        print(f"Heater on {system['device'].name}, waiting for 4He head to reach 3 K")

        with self.lock:


            heater_on(system['device'], system['He4_heater'])
            heater_on(system['device'], system['He3_heater'])


        print(f'sleeping 10 minutes, startint at {datetime.datetime.now()}')

        time.sleep(1800)
        print('waking up, startint to check')
        
            
        self.update_list_of_temperature(data_copy)

        while data_copy[f"LakeshoreModel372/{system['He4_head']}"][-1] > 3.1: #and isfinished(data_copy['time'], data_copy[f"LakeshoreModel372/{system['He4_head']}"]):
            time.sleep(2)
            self.update_list_of_temperature(data_copy)
        
        print(f"Heat switch on {system['device'].name}, waiting for 3He to reach 1.2 K")

        with self.lock:

            heater_off(system['device'], system['He4_heater'])
            switch_on(system['device'], system['He4_aio'])
            
        print(f'sleeping 10 minutes, startint at {datetime.datetime.now()}')
        time.sleep(600)
        print('waking up, startint to check')
        self.update_list_of_temperature(data_copy)
        time.sleep(20)

        self.update_list_of_temperature(data_copy)

        while data_copy[f"LakeshoreModel372/{system['He3_head']}"][-1] > 1.2: #and isfinished(data_copy['time'], data_copy[f"LakeshoreModel372/{system['He3_head']}"]):
            time.sleep(2)
            self.update_list_of_temperature(data_copy)


        print(f"Heat switch on on {system['device'].name}, waiting for 3He to reaching <450mK")
        with self.lock:

            heater_off(system['device'], system['He3_heater'])
            switch_on(system['device'], system['He3_aio'])
            
        print(f'sleeping 5 min starting at {datetime.datetime.now()}')
        time.sleep(300)
        self.update_list_of_temperature(data_copy)

        print('waking again, startint to check')
        while (condition_temperature := data_copy[f"LakeshoreModel372/{system['He3_head']}"][-1] > 0.450): #and (condition_stability := isfinished(data_copy['time'], data_copy[f"LakeshoreModel372/{system['He3_head']}"] )):
            time.sleep(2)
            self.update_list_of_temperature(data_copy)

        if not condition_temperature:
            print(f'walrus activated, sleeping 10 minutes starting at {datetime.datetime.now()}')
            time.sleep(600)
        print('Ready to switch system')

        return False

    
    
            
def switch_on(device, channel, voltage):
    IOtype_check = device.get_aio_iotype(channel)
    voltage_check = device.get_aio_voltage(channel)
    if IOtype_check == 'Set out':
        device.set_aio_voltage(channel, voltage)
    else:
        device.set_aio_iotype(channel, 'Set out')
        device.set_aio_voltage(channel, voltage)
        
def switch_off(device, channel):
    # aio_channel = device.aio_channels[channel]
    IOtype_check = device.get_aio_iotype(channel)
    voltage_check = device.get_aio_voltage(channel)
    if IOtype_check == 'Set out':
        if voltage_check > 1:
            device.set_aio_voltage(channel, 0)
        else:
            pass
        
def heater_PID_config(device, out_ch, in_ch):
    device.link_heater_to_input(out_ch, in_ch)
    device.write(f'{out_ch}.Units W')
    device.write(f"{out_ch}.HiLmt 1.8")
    device.write_setpoint(out_ch, 50)
    device.write(f'{out_ch}.Tune.Type Auto')
    device.enable_heater()
    device.tune_PID(out_ch, 0.5, 5)
    time.sleep(10)
    device.disable_PID(out_ch)
    device.write(f'{out_ch}.Off')
    
    
        
def heater_on(device, channel):
    device.enable_PID(channel)
    
    
def heater_off(device, channel):
    device.disable_PID(channel)
    device.set_heater_output(channel, 0)

def isfinished(time_buffer, temperature_buffer):
    try:
        Y = temperature_buffer[-1] - temperature_buffer[-20]
        X = time_buffer[-1] - time_buffer[-20]
        # X = X.total_seconds()
        slope = Y/X
        if slope > 0:
            return False
        else:
            return True
    except:
        return True
    
    


if __name__== "__main__":
    
    # ctc100A = SimulatedCTC100Device(port = 'A', name  = 'ctc100A')
    # ctc100B = SimulatedCTC100Device(port='B', name='ctc100B')
    # model224 = SimulatedLakeShore224Device(port = 'C', name = 'LakeshoreModel224')
    # model372 = SimulatedLakeShore372Device(port = 'D', name = 'LakeshoreModel350')



    '''Find and connect devices: you can add here new devices, make sure to identify them in the proper way (check the serial.tools.list_ports documentation) and to write a
    package to control your new device in the proper way (use CTC and lakeshore packages in this directory as an example)'''
    devices = serial.tools.list_ports.comports()


    for device in devices:
        if 'FT230X' in device.description:

            if 'DK0CDLQP' in device.serial_number:
                ctc100B = CTC100Device(address=device.device, name='ctc100B')
            elif 'DK0CDKFB' in device.serial_number:
                ctc100A = CTC100Device(address=device.device, name='ctc100A')
            else:
                print('Unknown device')
                pass
        if '224' in device.description:
            model224 = LakeShore224Device(
                port=device.device, name='LakeshoreModel224')
        if '372' in device.description:
            model372 = LakeShore372Device(port = device.device, name = 'LakeshoreModel372' )
            
    devices_list = [ctc100B, ctc100A, model224, model372]

    '''If you change the mapping of the channels you have to change these lists to!'''

    He7_B_channels = {'device': ctc100B, 'He4_head': model372.input_channels[1], 'He3_head': model372.input_channels[0], 'He4_pump': ctc100B.input_channels[2], 'He3_pump': ctc100B.input_channels[3], 'He4_switch': ctc100B.input_channels[
        0], 'He3_switch': ctc100B.input_channels[1], 'He4_heater': ctc100B.output_channels[0], 'He3_heater': ctc100B.output_channels[1], 'He4_aio': ctc100B.aio_channels[0], 'He3_aio': ctc100B.aio_channels[1]}
    He7_A_channels = {'device': ctc100A, 'He4_head': model372.input_channels[3], 'He3_head': model372.input_channels[2], 'He4_pump': ctc100A.input_channels[2], 'He3_pump': ctc100A.input_channels[3], 'He4_switch': ctc100A.input_channels[
        0], 'He3_switch': ctc100A.input_channels[1], 'He4_heater': ctc100A.output_channels[0], 'He3_heater': ctc100A.output_channels[1], 'He4_aio': ctc100A.aio_channels[0], 'He3_aio': ctc100A.aio_channels[1]}
    Dilution_refrigerator = {'Mixing_Chamber_SC': model372.input_channels[5], 'Mixing_Chamber_31206': model372.input_channels[8], 'Still': model372.input_channels[4], 'Split_Condenser': model372.input_channels[7]}


    # Initialise the databases folder
    database_dir = './DATA'
    if not os.path.exists(database_dir):
        os.mkdir(database_dir)


    # Initialise the database in hdf5
    CHUNK = 1
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shared_data = {}
    filename = f'{database_dir}/{today}_cooldown.hdf5'
    try:
        with h5py.File(f'{filename}', 'w-', libver='latest') as database:
            database.create_dataset('Time', shape=(
                CHUNK), chunks=True, maxshape=(None,))

            shared_data['time'] = []
            for device in devices_list:
                if device is model372:
                    tmp = database.create_group(f'{device.name}')

                    for channel in device.output_channels:
                        tmp.create_dataset(f'{channel}_percentage', shape=(
                            CHUNK), chunks=True, maxshape=(None,))
                        shared_data[f'{device.name}/{channel}'] = []
                    for channel in device.input_channels:
                        # if channel == '9':
                        #     tmp.create_dataset(f'{channel}_sensor', shape=(
                        #     CHUNK), chunks=True, maxshape=(None,))
                        #     shared_data[f'{device.name}/{channel}'] = []
                        # else:
                        tmp.create_dataset(f'{channel}_temperature', shape=(
                        CHUNK), chunks=True, maxshape=(None,))

                        shared_data[f'{device.name}/{channel}'] = []
                
                else:
                    tmp = database.create_group(f'{device.name}')
                    for channel in device.input_channels:
                        tmp.create_dataset(f'{channel}_temperature', shape=(
                            CHUNK), chunks=True, maxshape=(None,))
                    
                        shared_data[f'{device.name}/{channel}'] = []

    except:
        print(
            f'File {filename} already exists. Adding data to the existing file')
        # with h5py.File(f'{today}_cooldown.hdf5', 'a', libver='latest') as database:
        shared_data['time'] = []
        for device in devices_list:
            for channel in device.input_channels:
                shared_data[f'{device.name}/{channel}'] = []

    # database.swmr_mode = True


    serial_lock = Lock()
    
    data = Data_Acquisition(shared_data, filename,  lock = serial_lock, start_aq=True)
    cooldown = Cooldown_routine(shared_data, lock = serial_lock)
    

    print('starting')
    data.start()
    time.sleep(5)
    cooldown.start()
    
    data.join()
    cooldown.join()
