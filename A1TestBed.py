# -*- coding: utf-8 -*-
"""
Created on Thu Mar 28 14:14:27 2024

@author: tbates
"""

import automation1 as a1
import sys
import tkinter as tk
import time
from tkinter import messagebox, font, filedialog
from DecodeFaults import decode_faults
import json
import automation1.internal.exceptions_gen as a1_exceptions  # Import Automation1 exceptions

controller = None
non_virtual_axes = []
connected_axes = {}
controllers = {}

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

def multiple_controllers():
    global controllers
    #try:
    controller = a1.Controller.connect(host='10.101.3.198')
    controller_name = controller.name
    print('Controllers: ', controller_name)
    controller.start()
    running = controller.is_running
    print('Running: ', running)
    #except:
        #messagebox.showerror('No Device', 'No Devices Present. Check Connections.')
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

def connect():
    global controller, non_virtual_axes, connected_axes
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
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
            
            result = controller.runtime.status.get_status_items(status_item_configuration)
            axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
            if (axis_status & 1 << 13) > 0:
                connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
        for key, value in connected_axes.items():
            non_virtual_axes.append(key)
    else:
        for axis_index in range(0,32):
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
            result = controller.runtime.status.get_status_items(status_item_configuration)
            axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
            if (axis_status & 1 << 13) > 0:
                connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
        for key, value in connected_axes.items():
            print(f'Key: {key}')
            print(f'Value: {value}')
            non_virtual_axes.append(key)
    if len(non_virtual_axes) == 0:
        #try:
        controller = a1.Controller.connect_usb()
        number_of_axes = controller.runtime.parameters.axes.count
        if number_of_axes <= 12:
            for axis_index in range(0,11):
                status_item_configuration = a1.StatusItemConfiguration()
                status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
                
                result = controller.runtime.status.get_status_items(status_item_configuration)
                axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
                if (axis_status & 1 << 13) > 0:
                    connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
            for key, value in connected_axes.items():
                non_virtual_axes.append(key)
        else:
            for axis_index in range(0,32):
                status_item_configuration = a1.StatusItemConfiguration()
                status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
                result = controller.runtime.status.get_status_items(status_item_configuration)
                axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
                if (axis_status & 1 << 13) > 0:
                    connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
            for key, value in connected_axes.items():
                print(f'Key: {key}')
                print(f'Value: {value}')
                non_virtual_axes.append(key)
    print('Controller: ', controller.name)
    print('Axes present: ' , non_virtual_axes)
    #except:
        #messagebox.showerror('No Device', 'No Devices Present. Check Connections.')

def load_json():
    """Opens a file dialog to select a JSON file and loads it."""
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    json_path = filedialog.askopenfilename(title="Select JSON File", filetypes=[("JSON Files", "*.json")])

    if not json_path:
        print("No file selected.")
        return None
    
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data

def get_axis_data(data, axis_index=None):
    """Prompts the user for an axis index and retrieves parameters from the JSON data."""
    param_dict = {}
    if axis_index in data:
        print(f"\nParameters for Axis {axis_index}:")
        for param, value in data[axis_index].items():
            param_dict[param] = value
        print(f"Parameter Dictionary: {param_dict}")
    else:
        print(f"Axis {axis_index} not found in the JSON file.")

def test_runtime_params(data, axis=None, axis_index=None):
    """Prompts the user for an axis index and applies parameters using the API."""
    axis = str(axis)
    multiplier_value = controller.runtime.parameters.axes[axis].feedback.primaryencodermultiplicationfactor.value
    print('Multiplier: ', multiplier_value)
    if axis_index in data:
        print(f"\nApplying parameters to Axis {axis}...")
        
        for param, value in data[axis_index].items():
            # Properly format numbers and strings
            try:
                # Convert to float if it contains a decimal, otherwise int
                if isinstance(value, str) and value.replace('.', '', 1).lstrip('-').isdigit():
                    formatted_value = float(value) if '.' in value else int(value)
                else:
                    formatted_value = f'"{value}"'  # Wrap only actual strings in quotes

                # Construct the API command dynamically
                api_command = f"controller.runtime.parameters.axes['{axis}'][a1.AxisParameterId.{param}].value = {formatted_value}"

                # Simulate sending the command (Replace `exec` with actual API call)
                print(f"Executing: {api_command}")
                exec(api_command)  # Uncomment this line if you want it to actually execute

            except a1_exceptions.ControllerOperationException as e:
                print(f"⚠️ Warning: Cannot change '{param}' while the controller is running.")
                print(f"🛠️  Error Message: {e}")
                print(f"➡️  Try using configured parameters instead and restart the controller.")

            except TypeError as e:
                print(f"❌ Type Error: Cannot set '{param}' with value '{value}'.")
                print(f"🛠️  Ensure this parameter is of the correct type (int/float).")
                print(f"🔄 Skipping this parameter and continuing...")
        
        print(f"All parameters applied to Axis {axis}!")
    else:
        print(f"Axis {axis_index} not found in the JSON file.")
    multiplier_value = controller.runtime.parameters.axes[axis].feedback.primaryencodermultiplicationfactor.value
    print('Multiplier: ', multiplier_value)
def calibration():
    calibration_1d_file = controller.configuration.calibration_1d_file.get_configuration()
    calibration_2d_file = controller.configuration.calibration_2d_file.get_configuration()
    configured_parameters = controller.configuration.parameters.get_configuration()

    controller.configuration.calibration_1d_file.set_configuration(calibration_1d_file)
    controller.configuration.calibration_2d_file.set_configuration(calibration_2d_file)
    cal_file = (r'C:\Users\tbates\Documents\Automation1\637328-1-1-X.cal')

    with open(cal_file, 'r') as f:
        contents = f.read()

        controller.files.write_text('my_cal.cal', contents)

    controller.runtime.commands.calibration.calibrationload(a1.CalibrationType.AxisCalibration1D, 'my_cal.cal')
    print('Cal File: ' , calibration_1d_file)

def limits(axis):
    electrical_limits = controller.runtime.parameters.axes[axis].protection.faultmask
    eot_limit_setup = controller.runtime.parameters.axes[axis].protection.endoftravellimitsetup.value
    electrical_limit_value = int(electrical_limits.value)
    print('Fault Mask: ',electrical_limit_value)
    print('EOT Limit Setup: ', eot_limit_setup)
    #all_limits_on = 1355157503

    # Find the mask
    #mask = all_limits_on ^ electrical_limit_value
    if (electrical_limit_value & 1 << 5) > 0:
        print("Ccw software limit on")
    else: 
        print("Ccw software limit off")

    if (electrical_limit_value & 1 << 4) > 0:
        print("Cw software limit on")
    else: 
        print("Cw software limit off")

    if (electrical_limit_value & 1 << 3) > 0:
        print("Ccw electrical limit on")
    else: 
        print("Ccw electrical limit off")

    if (electrical_limit_value & 1 << 2) > 0:
        print("Cw electrical limit on")
    else: 
        print("Cw electrical limit off")

    # Print the result
    #print(f"Mask: {mask}, Binary: {bin(mask)}")

def absolute_encoder():
    absolute = int(controller.runtime.parameters.axes['ST01'].feedback.primaryfeedbacktype.value)
    print('Aux Feedback Type: ',absolute)

    absolute_offset = controller.runtime.parameters.axes['ST01'].feedback.auxiliaryabsolutefeedbackoffset.value
    homesetup_dec_val = int(controller.runtime.parameters.axes['ST01'].homing.homesetup.value)
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

    print('Absolute Offset: ', absolute_offset)

def halls():
    halls = {}

    data_config = a1.DataCollectionConfiguration(1000,a1.DataCollectionFrequency.Frequency1kHz)  #Freq should be 20x the max frequency required by end process
    data_config.system.add(a1.SystemDataSignal.DataCollectionSampleTime)
    data_config.axis.add(a1.AxisDataSignal.DriveStatus, 'ST01')
    data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, 'ST01')

    controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)

    results = controller.runtime.data_collection.get_results(data_config, 1000)

    halls['ST01'] = results.axis.get(a1.AxisDataSignal.DriveStatus, 'ST01').points

    pri_fbk = results.axis.get(a1.AxisDataSignal.PrimaryFeedback, 'ST01').points

    print(halls)
    for x in halls:
        hall_a_ST1 = [1 if ((int(x) & a1.DriveStatus.HallAInput.value) > 0) else 0]
        hall_b_ST1 = [1 if ((int(x) & a1.DriveStatus.HallBInput.value) > 0) else 0]
        hall_c_ST1 = [1 if ((int(x) & a1.DriveStatus.HallCInput.value) > 0) else 0]

        hall_a_ST2 = [1 if ((int(x) & a1.DriveStatus.HallAInput.value) > 0) else 0]
        hall_b_ST2 = [1 if ((int(x) & a1.DriveStatus.HallBInput.value) > 0) else 0]
        hall_c_ST2 = [1 if ((int(x) & a1.DriveStatus.HallCInput.value) > 0) else 0]
    
    print('Hall a for ST1: ', hall_a_ST1)
    print('Hall a for ST2: ', hall_a_ST2)

def get_pos_fbk():
    status_item_configuration = a1.StatusItemConfiguration()
    status_item_configuration.axis.add(a1.AxisStatusItem.PositionFeedback, "ST01")
    # Retrieve position feedback from the controller
    results = controller.runtime.status.get_status_items(status_item_configuration)
    print(results)
    # Retrieve position feedback and round to 4 decimal places
    stage_limit_pos = round(results.axis.get(a1.AxisDataSignal.PositionFeedback, 'ST01').value, 4)

    return stage_limit_pos

def check_for_faults():
    print('Checking For Faults')
    faults = {}  # Initialize an empty dictionary to store results per axis
    
    for axis in non_virtual_axes:
        status_item_configuration = a1.StatusItemConfiguration()
        status_item_configuration.axis.add(a1.AxisStatusItem.AxisFault, axis)
        
        # Get the results for the current axis
        results = controller.runtime.status.get_status_items(status_item_configuration)
        
        # Extract the axis fault status as an integer
        axis_faults = int(results.axis.get(a1.AxisStatusItem.AxisFault, axis).value)
        # Store the axis_faults in the self.faults dictionary with the axis as the key
        faults[axis] = axis_faults  # Store the result in the dictionary with the axis as the key
        
    return faults

def main(test=None):
    """Main function to load JSON and get parameters for an axis."""
    if test == 'Params':
        data = load_json()
        if data:
            axis_index = input("Enter the Axis Index to retrieve parameters: ")
            get_axis_data(data, axis_index)
    if test == 'Limits':
        connect()
        axis = input('Enter the axis to check limits: ')
        limits(axis)
    if test == 'Test Runtime':
        connect()
        data = load_json()
        if data:
            #axis_index = input("Enter the Axis Index to retrieve parameters: ")
            get_axis_data(data, axis_index='2')
        #axis = input('Enter the axis you want to insert params for: ')
        test_runtime_params(data, axis='ST03', axis_index='2')
    if test == 'Multiple Controllers':
        multiple_controllers()
main(test='Multiple Controllers')
