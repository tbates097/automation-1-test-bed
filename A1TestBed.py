# -*- coding: utf-8 -*-
"""
Created on Thu Mar 28 14:14:27 2024

@author: tbates
"""

import automation1 as a1
import sys
import tkinter as tk
from tkinter import messagebox, font

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
print('Fault Mask: ',electrical_limit_value)

#controller.runtime.commands.calibration.calibrationload(a1.CalibrationType.AxisCalibration1D, 'my_cal.cal')
absolute = int(controller.runtime.parameters.axes['X'].feedback.primaryfeedbacktype.value)
print('Aux Feedback Type: ',absolute)

absolute_offset = controller.runtime.parameters.axes['X'].feedback.auxiliaryabsolutefeedbackoffset.value
homesetup_dec_val = int(controller.runtime.parameters.axes['X'].homing.homesetup.value)
print('Home Setup: ', homesetup_dec_val)

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

data_config = a1.DataCollectionConfiguration(1000,a1.DataCollectionFrequency.Frequency1kHz)  #Freq should be 20x the max frequency required by end process
data_config.system.add(a1.SystemDataSignal.DataCollectionSampleTime)
data_config.axis.add(a1.AxisDataSignal.DriveStatus, 'X')
data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, 'X')

results = controller.runtime.data_collection.collect_snapshot(data_config)

halls = results.axis.get(a1.AxisDataSignal.DriveStatus, 'X').points

hall_a = [1 if ((int(x) & a1.DriveStatus.HallAInput.value) > 0) else 0 for x in halls]
hall_b = [1 if ((int(x) & a1.DriveStatus.HallBInput.value) > 0) else 0 for x in halls]
hall_c = [1 if ((int(x) & a1.DriveStatus.HallCInput.value) > 0) else 0 for x in halls]

pri_fbk = results.axis.get(a1.AxisDataSignal.PrimaryFeedback, 'X').points


