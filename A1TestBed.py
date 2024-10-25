# -*- coding: utf-8 -*-
"""
Created on Thu Mar 28 14:14:27 2024

@author: tbates
"""

import automation1 as a1
import sys
import tkinter as tk
import time
from tkinter import messagebox, font
from DecodeFaults import decode_faults

fault_dict = {
        'PositionErrorFault': 1 << 0,
        'OverCurrentFault': 1 << 1,
        'CwEndOfTravelLimitFault': 1 << 2,
        'CcwEndOfTravelLimitFault': 1 << 3,
        'CwSoftwareLimitFault': 1 << 4,
        'CcwSoftwareLimitFault': 1 << 5,
        'AmplifierFault': 1 << 6,
        'FeedbackInput0Fault': 1 << 7,
        'FeedbackInput1Fault': 1 << 8,
        'HallSensorFault': 1 << 9,
        'MaxVelocityCommandFault': 1 << 10,
        'EmergencyStopFault': 1 << 11,
        'VelocityErrorFault': 1 << 12,
        'ExternalFault': 1 << 15,
        'MotorTemperatureFault': 1 << 17,
        'AmplifierTemperatureFault': 1 << 18,
        'EncoderFault': 1 << 19,
        'GantryMisalignmentFault': 1 << 22,
        'FeedbackScalingFault': 1 << 23,
        'MarkerSearchFault': 1 << 24,
        'SafeZoneFault': 1 << 25,
        'InPositionTimeoutFault': 1 << 26,
        'VoltageClampFault': 1 << 27,
        'MotorSupplyFault': 1 << 28,
        'InternalFault': 1 << 30,
    }


sys.stdout = sys.__stdout__
root = tk.Tk()
root.withdraw()

def controller_def():
    ver = tk.Toplevel(root)
    ver.title('Connection Type')
    ver.configure(bg='white')

    custom_font = font.Font(family="Times New Roman", size=12, weight="bold", slant="italic")

    label = tk.Label(ver, text="Are you trying to connect via USB?", bg='white', font=custom_font)
    label.grid(row=0, column=0, columnspan=2, padx=10, pady=5)

    def on_yes():
        ver.result = 'yes'
        ver.destroy()

    def on_no():
        ver.result = 'No'
        ver.destroy()

    button_ok = tk.Button(ver, text="Yes", width=10, height=2, command=on_yes)
    button_ok.grid(row=4, column=0, padx=10, pady=10)

    button_cancel = tk.Button(ver, text="No", width=10, height=2, command=on_no)
    button_cancel.grid(row=4, column=1, padx=10, pady=10)

    ver.resizable(False, False)

    ver.update_idletasks()  # Ensure that the window sizes correctly

    screen_width = ver.winfo_screenwidth()
    screen_height = ver.winfo_screenheight()

    ver_width = ver.winfo_reqwidth()
    ver_height = ver.winfo_reqheight()

    x_cordinate = int((screen_width / 2) - (ver_width / 2))
    y_cordinate = int((screen_height / 2) - (ver_height / 2))

    ver.geometry("{}x{}+{}+{}".format(ver_width, ver_height, x_cordinate, y_cordinate))
    ver.focus_set()
    ver.result = None
    ver.wait_window()

    return ver.result

try:
    controller = a1.Controller.connect()
    controller.start()
except:
    connection_type = controller_def()
    if connection_type == 'yes':
        try:
            controller = a1.Controller.connect_usb()
            controller.start()
        except:
            messagebox.showerror('Connection Error', 'Check connections and try again')
    else:
        messagebox.showerror('Update Software', 'Update Hyperwire firmware and try again')
connected_axes = {}
non_virtual_axes = []

number_of_axes = controller.runtime.parameters.axes.count

if number_of_axes <= 12:
    for axis_index in range(0,11):

        #try:            
        # Create status item configuration object
        status_item_configuration = a1.StatusItemConfiguration()
                    
        # Add this axis status word to object
        status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
        
        # Get axis status word from controller
        result = controller.runtime.status.get_status_items(status_item_configuration)
        axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
        
        # Check NotVirtual bit of axis status word
        if (axis_status & 1 << 13) > 0:
            connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
        #except:
            #print('2')
            #for key in connected_axes.items():
                #if key == axis:
                    #print(key)
                    #break
            #else:
                #print('3')
                #axis_no += 1
                #pass

    for key,value in connected_axes.items():
        non_virtual_axes.append(key)
        
    if len(non_virtual_axes) == 0:
        try:
            controller = a1.Controller.connect_usb()
        except:
            messagebox.showerror('No Device', 'No Devices Present. Check Connections.')    
else:
    for axis_index in range(0,32):
    
        #try:            
        # Create status item configuration object
        status_item_configuration = a1.StatusItemConfiguration()
                    
        # Add this axis status word to object
        status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
        
        # Get axis status word from controller
        result = controller.runtime.status.get_status_items(status_item_configuration)
        axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
        
        # Check NotVirtual bit of axis status word
        if (axis_status & 1 << 13) > 0:
            connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
        #except:
            #print('2')
            #for key in connected_axes.items():
                #if key == axis:
                    #print(key)
                    #break
            #else:
                #print('3')
                #axis_no += 1
                #pass
    
    for key,value in connected_axes.items():
        non_virtual_axes.append(key)
        
    if len(non_virtual_axes) == 0:
        try:
            controller = a1.Controller.connect_usb()
        except:
            messagebox.showerror('No Device', 'No Devices Present. Check Connections.')

#calibration_1d_file = controller.configuration.calibration_1d_file.get_configuration()
#calibration_2d_file = controller.configuration.calibration_2d_file.get_configuration()
#configured_parameters = controller.configuration.parameters.get_configuration()

#controller.configuration.calibration_1d_file.set_configuration(calibration_1d_file)
#controller.configuration.calibration_2d_file.set_configuration(file_2d)
#cal_file = (r'C:\Users\tbates\Documents\Automation1\637328-1-1-X.cal')

#with open(cal_file, 'r') as f:
    #contents = f.read()

    #controller.files.write_text('my_cal.cal', contents)

electrical_limits = controller.runtime.parameters.axes['X'].protection.faultmask
electrical_limit_value = int(electrical_limits.value)
#print('Fault Mask: ',electrical_limit_value)

#controller.runtime.commands.calibration.calibrationload(a1.CalibrationType.AxisCalibration1D, 'my_cal.cal')
absolute = int(controller.runtime.parameters.axes['X'].feedback.primaryfeedbacktype.value)
#print('Aux Feedback Type: ',absolute)

absolute_offset = controller.runtime.parameters.axes['X'].feedback.auxiliaryabsolutefeedbackoffset.value
homesetup_dec_val = int(controller.runtime.parameters.axes['X'].homing.homesetup.value)
#print('Home Setup: ', homesetup_dec_val)

if absolute == 1:
    encoder = 'IncrementalEncoderSquareWave'
elif absolute == 2:
    encoder = 'IncrementalEncoderSineWave'
elif absolute == 4:
    encoder = 'AbsoluteEncoderEnDat'
elif absolute == 6:
    encoder = 'AbsoluteEncoderSSI'
elif absolute == 9:
    encoder = 'AbsoluteEncoderBiSS'
else:
    encoder = 'None'

print('Controller: ', controller.name)
print('Axes present: ' , non_virtual_axes)
#print('Absolute Offset: ', absolute_offset)
#print('Home Direction: ', homesetup_dec_val)
#print('Encoder Type: ', encoder)
#print('Cal File: ' , calibration_1d_file)
#print('Configured Params: ' , configured_parameters)
halls = {}
for axis in non_virtual_axes:
    print("Axis: ", axis)
    data_config = a1.DataCollectionConfiguration(1000,a1.DataCollectionFrequency.Frequency1kHz)  #Freq should be 20x the max frequency required by end process
    data_config.system.add(a1.SystemDataSignal.DataCollectionSampleTime)
    data_config.axis.add(a1.AxisDataSignal.DriveStatus, axis)
    data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, axis)

controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)

results = controller.runtime.data_collection.get_results(data_config, 1000)

for axis in non_virtual_axes:
    halls[axis] = results.axis.get(a1.AxisDataSignal.DriveStatus, axis).points
    
print(halls)
#hall_a_ST1 = [1 if ((int(x) & a1.DriveStatus.HallAInput.value) > 0) else 0 for x in halls_ST1]
#hall_b_ST1 = [1 if ((int(x) & a1.DriveStatus.HallBInput.value) > 0) else 0 for x in halls_ST1]
#hall_c_ST1 = [1 if ((int(x) & a1.DriveStatus.HallCInput.value) > 0) else 0 for x in halls_ST1]

#hall_a_ST2 = [1 if ((int(x) & a1.DriveStatus.HallAInput.value) > 0) else 0 for x in halls_ST2]
#hall_b_ST2 = [1 if ((int(x) & a1.DriveStatus.HallBInput.value) > 0) else 0 for x in halls_ST2]
#hall_c_ST2 = [1 if ((int(x) & a1.DriveStatus.HallCInput.value) > 0) else 0 for x in halls_ST2]

pri_fbk = results.axis.get(a1.AxisDataSignal.PrimaryFeedback, 'ST1').points

# =============================================================================
# def check_for_faults():
#     print('Checking For Faults')
#     faults = {}  # Initialize an empty dictionary to store results per axis
#     #decoded_faults_per_axis = {}  # Dictionary to store decoded faults for each axis
#     
#     for axis in non_virtual_axes:
#         status_item_configuration = a1.StatusItemConfiguration()
#         status_item_configuration.axis.add(a1.AxisStatusItem.AxisFault, axis)
#         
#         # Get the results for the current axis
#         results = controller.runtime.status.get_status_items(status_item_configuration)
#         
#         # Extract the axis fault status as an integer
#         axis_faults = int(results.axis.get(a1.AxisStatusItem.AxisFault, axis).value)
#         setup_axes = controller.
#         # Store the axis_faults in the self.faults dictionary with the axis as the key
#         faults[axis] = axis_faults  # Store the result in the dictionary with the axis as the key
#         
#     return faults
# =============================================================================
print(non_virtual_axes)
#print('Hall a for ST1: ', hall_a_ST1)
#print('Hall a for ST2: ', hall_a_ST2)


# =============================================================================
# controller.runtime.commands.motion.enable(non_virtual_axes)
# controller.runtime.commands.motion.home(non_virtual_axes)
# #controller.runtime.commands.motion.movefreerun(['ST1'], [10])
# time.sleep(5)
# 
# faults_per_axis = check_for_faults()
# 
# fault_init = decode_faults(faults_per_axis, non_virtual_axes, controller)
# fault_init.get_fault()
# controller.runtime.commands.motion.waitformotiondone(["ST1"])
# =============================================================================



