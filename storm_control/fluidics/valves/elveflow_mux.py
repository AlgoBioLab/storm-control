#!/usr/bin/python
# ----------------------------------------------------------------------------------------
# For Elveflow MUX Distribution Valves
# ----------------------------------------------------------------------------------------
import time

import sys
sys.path.append('C:/Users/RPI/Desktop/ESI_V3_07_04/ESI_V3_07_04/SDK_V3_07_04/SDK_V3_07_04/SDK_V3_07_04/Python_64/DLL64')#add the path of the library here
sys.path.append('C:/Users/RPI/Desktop/ESI_V3_07_04/ESI_V3_07_04/SDK_V3_07_04/SDK_V3_07_04/SDK_V3_07_04/Python_64')#add the path of the LoadElveflow.py

from ctypes import *

from array import array

from Elveflow64 import *

from storm_control.fluidics.valves.valve import AbstractValve

class AValveChain(AbstractValve):
    def __init__(self,
                 parameters):

        # Unlike other models, Elveflow valves each use their own COM port.
        self.com_ports = parameters.get("valve_com_ports")
        self.verbose = parameters.get("verbose", False)
        self.num_simulated_valves = parameters.get("num_simulated_valves", 0)
        self.simulate = (self.num_simulated_valves > 0)

        # Define valve and port properties
        self.num_valves = 0 # Set in initialSetup; depends on kilroy configuration.
        self.valve_dri_ids = [] # Set in initialSetup.
        self.simulated_valve_posns = [] # Only for simulation.
        # max_ports_per_valve currently only used for generating Qt port menu.
        # Assume all MUX 12/1 valves; if this changes, can configure in kilroy settings
        # and adjust code. Other modules build a list on initialization, but Elveflow
        # Mux valves can't be queried for their port configuration.
        self.max_ports_per_valve = 12

        # Configure device
        self.initialSetup()


    def initialSetup(self):
        if self.verbose: print("Setting up Elveflow valve chain.")

        if self.simulate:
            self.num_valves = self.num_simulated_valves
            self.simulated_valve_posns = [0 for i in range(self.num_valves)]
            print(f"Simulating {self.num_valves} Elveflow MUX valves.")
            return
        #for com_port in self.com_ports.getAttrs():
        #import pdb; pdb.set_trace()
        for i in [8,9,10]:
            # MUX_DRI_Initialization - give visa COM port, get MUX DRI ID.
            # It might want ASRLX[X]::INSTR instead of COMX[X].
            Instr_ID=c_int32()
            
            #valve_dri_id=MUX_DRI_Initialization(f"COM{i}".encode('ascii'),byref(Instr_ID))
            valve_dri_id=MUX_DRI_Initialization(f"ASRL{i}::INSTR".encode('ascii'),byref(Instr_ID))
            self.valve_dri_ids.append(Instr_ID.value)
            #print(com_port)
            print(valve_dri_id)
            # check for error code and raise exception if fail.
        print(self.valve_dri_ids)
        self.num_valves = len(self.valve_dri_ids)

        # Home the valves
        print("Homing valves.")
        # MUX_DRI_Send_Command
        Answer=(c_char*40)()
        for valv_id in self.valve_dri_ids:
            error=MUX_DRI_Send_Command(valv_id,0,Answer,40)
            time.sleep(15)


    def changePort(self, valve_ID, port_ID, direction = 0):
        # A note on valve/port indexing, for future persons tempted to clean up these +1s:
        #   ValveCommands.parseCommandXML will read the Kilroy commands_file and
        #   decrement the valve_ID and port_ID before constructing a ValveCommand.
        #   This means that it is 'Kilroy policy' to treat user-facing valve/port
        #   IDs as 1-indexed, but 'code-facing' valve/port IDs as 0-indexed.
        #   (Qt also enumerates the dropdown menu ports in 0-index.)

        if self.verbose:
            print(f"Changing valve {valve_ID+1} to port {port_ID+1}"
                  f" in {['shortest', 'clockwise', 'counter-clockwise'][direction]} direction.")
        if self.simulate:
            self.simulated_valve_posns[valve_ID] = port_ID
            return

        # MUX_DRI_Set_Valve
        port_ID=int(port_ID+1)
        port_ID=c_int32(port_ID)
        print(valve_ID)
        print(port_ID)
        error=MUX_DRI_Set_Valve(valve_ID,port_ID,direction)


    def howManyValves(self):
        return self.num_valves


    def close(self):
        if self.verbose:
            print("Closing valve connection.")
        if self.simulate:
            return

        # MUX_DRI_Destructor

        for valv_id in self.valve_dri_ids:
            error=MUX_DRI_Destructor(valv_id)


    def getDefaultPortNames(self, valve_ID):
        # This module doesn't care about the valve_ID;
        # see note above on max_ports_per_valve.
        return [f"Port {i+1}" for i in range(self.max_ports_per_valve)]


    def howIsValveConfigured(self, valve_ID):
        # see note above on max_ports_per_valve.
        return "12 ports"


    def getStatus(self, valve_ID):
        # Returns a tuple that is consumed by QtValveControl.setStatus:
        # ("this valve's current port", "is valve still moving").

        if self.simulate:
            return (f"Port {self.simulated_valve_posns[valve_ID]+1}", False)

        # MUX_DRI_Get_Valve
        port = 900 #change this to whatever Get Valve returns

        if port == 0:
            return ("Changing", True)
        else:
            return (f"Port {port+1}", False)

    def resetChain(self):
        if self.verbose:
            print("User called Elveflow resetChain.")
            print("NB: The Elveflow module cannot auto-detect valve and port configurations; "
                  "to reconfigure your valve setup please edit your Kilroy settings and "
                  "restart Kilroy.")

            print("\nHoming valves.")
        if self.simulate:
            return

        # Home the valves
        # MUX_DRI_Send_Command

        Answer=(c_char*40)()
        for valv_id in self.valve_dri_ids:
            error=MUX_DRI_Send_Command(valv_id,0,Answer,40)
            time.sleep(15)


    def getRotationDirections(self, valve_ID):
        # These get enumerated by Qt to ints 0, 1, 2 and passed to changePort;
        # then MUX_DRI_Set_Valve understands 0-shortest, 1-clockwise, 2-counterclockwise.
        # So: don't change the ordering.
        return ("Shortest", "Clockwise", "Counter Clockwise")
