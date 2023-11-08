#!/usr/bin/python
# ----------------------------------------------------------------------------------------
# Elveflow OB1 MK4 pressure & vacuum flow controller
# ----------------------------------------------------------------------------------------

# TODO: for dlls:
import ctypes

class APump():
    """ Elveflow OB1 MK4 """

    def __init__(self,
                 parameters = False):

        # Define attributes
        self.identification = "Elveflow OB1" # For GUI only
        self.pump_ID = parameters.get("pump_id", -1) # OB1 ID
        self.verbose = parameters.get("verbose", True)
        self.simulate = parameters.get("simulate_pump", False)
        self.set_channel = parameters.get("channel", 1)
        # TODO: Likely need to add channel info here and to the Kilroy settings

        # Define initial pump status
        self.flow_status = "Stopped"
        self.speed = 0.0

        # Configure pump
        self.configurePump()


    def configurePump(self):
        if self.simulate:
            print("Simulating Elveflow OB1")
            return

        # TODO.
        # OB1_Initialization
        Instr_ID=c_int32()
        print("Instrument name and regulator types are hardcoded in the Python script")
        error=OB1_Initialization('01A1E91E'.encode('ascii'),1,2,4,3,byref(Instr_ID))
        #all functions will return error codes to help you to debug your code, for further information refer to User Guide
        print('error:%d' % error)
        print("OB1 ID: %d" % Instr_ID.value)
        error=OB1_Add_Sens(Instr_ID, 1, 4, 1, 0, 7, 0) # TODO fix parameters
        #(CustomSens_Voltage_5_to_25 only works with CustomSensors and OB1 from 2020 and after)
        print('error add digit flow sensor:%d' % error)
        # OB1_Add_Sens
        error=OB1_Add_Sens(Instr_ID, 1, 5, 0, 0, 7, 0) # TODO fix parameters
        #(CustomSens_Voltage_5_to_25 only works with CustomSensors and OB1 from 2020 and after)
        print('error add analog flow sensor:%d' % error)
        Calib=(c_double*1000)()
        # OB1_Start_Remote_Measurement
        OB1_Start_Remote_Measurement(Instr_ID.value, byref(Calib), 1000)
        #

        self.pump_ID = Instr_ID.value # set to whatever is returned by _Initialization; check that it is not -1


    def calibratePump(self):
        if self.simulate:
            print("Calibrating simulated OB1 pump")
            return

        # TODO
        # OB1_Calib
        Calib=(c_double*1000)()#always define array this way, calibration should have 1000 elements
        error=Elveflow_Calibration_Default (byref(Calib),1000)
        #for i in range (0,1000):
        #    print('[',i,']: ',Calib[i])
        # See also Elveflow_Calibration_[Default,Save,Load]
        # May have to stop remote workflow, calibrate, and then restart remote workflow
        # Otherwise, would have to check if loop is active on every setSpeed - not sure if possible/practical




    def getStatus(self):
        if self.simulate:

            return [self.flow_status, self.speed]
        data_sens=c_double()
        error=OB1_Get_Remote_Data(Instr_ID.value,self.set_channel, 1,byref(data_sens))
        self.speed = data_sens.value
        if self.speed = 0:
            self.flow_status = "Stopped"
        else:
            self.flow_status = "Flowing"
        # TODO
        # Set self.flow_status and self.speed
        # Probably according to output of OB1_Get_Remote_Data
        # See also
        # OB1_Get_Press, OB1_Get_Sens_Data

        return [self.flow_status, self.speed]


    def close(self):
        if self.simulate:
            print("Closed simulated OB1 pump.")
            
            return
        error=OB1_Stop_Remote_Measurement(Instr_ID.value)
        error=OB1_Destructor(Instr_ID.value)
        # TODO OB1_Stop_Remote_Measurement
        # TODO OB1_Destructor


    def setSpeed(self, speed):
        if self.verbose: print("Setting pump speed to " + str(speed))

        if self.simulate:
            self.speed = speed
        error=OB1_Set_Remote_Target(Instr_ID.value, self.set_channel, speed)
            

        # TODO
        # Probably OB1_Set_Remote_Target and not OB1_Set_Press


    def startFlow(self, speed, direction = "Forward"):
        if not direction == "Forward":
            print("Error setting direction: Reverse direction not implemented for Elveflow OB1. Stopping pump")
            self.stopFlow()
            return

        if self.simulate:
            self.flow_status = "Flowing"

        self.setSpeed(speed)


    def stopFlow(self):
        if self.simulate:
            self.flow_status = "Stopped"

        self.setSpeed(0.0)


#
# The MIT License
#
# Copyright (c) 2021 Moffitt Laboratory, Boston Children's Hospital
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

