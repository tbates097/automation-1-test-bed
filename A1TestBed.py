# -*- coding: utf-8 -*-
"""
Created on Thu Mar 28 14:14:27 2024

@author: tbates
"""

import automation1 as a1
import sys
import tkinter as tk
import time
import numpy as np
import serial.tools.list_ports
from tkinter import messagebox, font, filedialog
from DecodeFaults import decode_faults
import json
import threading
import automation1.internal.exceptions_gen as a1_exceptions  # Import Automation1 exceptions

station_lock = threading.Lock()
stations = []
test_axes = []

# Initialize hall sensor dictionaries
hall_a = {}
hall_b = {}
hall_c = {}
hall_states = {}
hall_encoder_positions = {}
pri_fbk = {}
ccw_fault = {}
cw_fault = {}
pos_error_fault = {}
over_current_fault = {}
        
controller = None
non_virtual_axes = []
connected_axes = {}
controllers = {}

station_dict = {
    'ST01': '192.168.1.15',
    'ST02': '192.168.1.16',
    'ST03': '192.168.1.17'
}

station_states = {
    'ST01': {
        "status": "free",
        "thread": None,
        "serial_number": None,
        "axis_name": "ST01",
        "program_id": None,
        "controllers": None
    },
    'ST02': {
        "status": "free",
        "thread": None,
        "serial_number": None,
        "axis_name": "ST02",
        "program_id": None,
        "controllers": None
    },
    'ST03': {
        "status": "free",
        "thread": None,
        "serial_number": None,
        "axis_name": "ST03",
        "program_id": None,
        "controllers": None
    }
}

def allocate_stations(num_stations, program_id):
    """Allocate the required number of free stations, or return None if not enough are available."""
    try:
        if not station_lock.acquire(timeout=5):
            print("Could not acquire station lock - timeout")
            return None
            
        free_stations = [
            station for station in ['ST01', 'ST02', 'ST03']
            if station_states[station]["status"] == "free"
        ]
        print(f"Found {len(free_stations)} free stations: {free_stations}")
        
        if len(free_stations) >= num_stations:
            allocated = free_stations[:num_stations]
            print(f"Allocating stations: {allocated}")
            for station in allocated:
                station_states[station].update({
                    "status": "in-use",
                    "program_id": program_id
                })
            return allocated
        
        print(f"Not enough free stations. Need {num_stations}, found {len(free_stations)}")
        return None
    except Exception as e:
        print(f"Error in allocate_stations: {str(e)}")
        return None
    finally:
        try:
            station_lock.release()
            print("Released station lock")
        except RuntimeError:
            pass

def release_stations(stations):
    """Release multiple stations and mark them as free."""
    with station_lock:
        program_id = id(threading.current_thread())
        for station in stations:
            if station_states[station]["program_id"] == program_id:
                # Only release if this program owns the station
                if station_states[station]["controllers"]:
                    try:
                        station_states[station]["controllers"].disconnect()
                    except:
                        pass
                station_states[station].update({
                    "status": "free",
                    "thread": None,
                    "serial_number": None,
                    "program_id": None,
                    "controllers": None
                })

def get_station_controller(station):
    """Safely get controller for a station."""
    program_id = id(threading.current_thread())
    with station_lock:
        if station_states[station]["status"] == "in-use":
            print(f"Debug - Station {station}:")
            print(f"  Thread ID: {program_id}")
            print(f"  Station program_id: {station_states[station]['program_id']}")
            print(f"  Status: {station_states[station]['status']}")
            if station_states[station]["controllers"]:
                return station_states[station]["controllers"]
    return None

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

def get_limit_dec(controller, axis, limit=None):
    # Retrieve the current configuration for the axis
    electrical_limits = controller.runtime.parameters.axes[axis].protection.faultmask
    electrical_limit_value = int(electrical_limits.value)

    # Define bit positions for each limit
    CCW_SOFTWARE_LIMIT = 5
    CW_SOFTWARE_LIMIT = 4
    CCW_ELECTRICAL_LIMIT = 3
    CW_ELECTRICAL_LIMIT = 2

    # Toggle limits
    if limit == 'software on':
        electrical_limit_value |= (1 << CCW_SOFTWARE_LIMIT) | (1 << CW_SOFTWARE_LIMIT)
    elif limit == 'software off':
        electrical_limit_value &= ~((1 << CCW_SOFTWARE_LIMIT) | (1 << CW_SOFTWARE_LIMIT))
    elif limit == 'electrical on':
        electrical_limit_value |= (1 << CCW_ELECTRICAL_LIMIT) | (1 << CW_ELECTRICAL_LIMIT)
    elif limit == 'electrical off':
        electrical_limit_value &= ~((1 << CCW_ELECTRICAL_LIMIT) | (1 << CW_ELECTRICAL_LIMIT))

    return electrical_limit_value

def params(controller, axis, home_offset=None, current_clamp=None, limit=None):
    """
    Configure parameters for a specific axis on its controller.

    Args:
        controller: The controller object for this specific axis
        axis: The axis to configure
        home_offset (int): The home offset value for the axis
        current_clamp (float): The maximum current clamp value
        limit (str): The fault mask limits (e.g., 'software on', 'software off')
    """
    # Retrieve current configuration parameters for the axis
    configured_parameters = controller.configuration.parameters.get_configuration()
    
    if home_offset:
        home_offset_before = controller.runtime.parameters.axes[axis].homing.homeoffset.value
        print(f'Home Offset Before: {home_offset_before}')
        configured_parameters.axes[axis].homing.homeoffset.value = home_offset
        home_offset_after = controller.runtime.parameters.axes[axis].homing.homeoffset.value
        print(f'Home Offset After: {home_offset_after}')
    if home_offset == 0:
        home_offset_before = controller.runtime.parameters.axes[axis].homing.homeoffset.value
        print(f'Home Offset Before: {home_offset_before}')
        configured_parameters.axes[axis].homing.homeoffset.value = 0
        home_offset_after = controller.runtime.parameters.axes[axis].homing.homeoffset.value
        print(f'Home Offset After: {home_offset_after}')


    if current_clamp:
        current_clamp_before = controller.runtime.parameters.axes[axis].protection.maxcurrentclamp.value
        print(f'Current Clamp Before: {current_clamp_before}')
        configured_parameters.axes[axis].protection.limitdebouncedistance.value = 1
        configured_parameters.axes[axis].protection.maxcurrentclamp.value = current_clamp
        current_clamp_after = controller.runtime.parameters.axes[axis].protection.maxcurrentclamp.value
        print(f'Current Clamp After: {current_clamp_after}')

    if limit:
        limit_before = controller.runtime.parameters.axes[axis].protection.faultmask.value
        print(f'Limit Before: {limit_before}')
        electrical_limit_value = get_limit_dec(controller, axis, limit)
        configured_parameters.axes[axis].protection.faultmask.value = electrical_limit_value
        limit_after = controller.runtime.parameters.axes[axis].protection.faultmask.value
        print(f'Limit After: {limit_after}')

    # Apply the updated configuration for the axis
    controller.configuration.parameters.set_configuration(configured_parameters)

def reset_controllers():
    """
    Reset all controllers in parallel using threads.
    Waits for all resets to complete before returning.
    """
    global test_axes
    threads = []
    
    def reset_single_controller(station):
        if not isinstance(station, str):
            print(f"Invalid station format: {station}")
            return
            
        if station not in station_states:
            print(f"Unknown station: {station}")
            return
            
        controller = get_station_controller(station)
        try:
            if controller:
                print(f"Resetting controller for station {station}")
                controller.reset()
                print(f"Reset completed for station {station}")
            else:
                print(f"No controller found for station {station}")
            
        except Exception as e:
            print(f"Error resetting station {station}: {str(e)}")
    
    # Ensure we're working with complete station names
    if isinstance(test_axes, str):
        test_axes = [test_axes]  # Convert single station to list
        
    # Filter out any invalid stations
    valid_stations = [station for station in test_axes if station in station_states]
    
    if not valid_stations:
        print(f"No valid stations found in: {test_axes}")
        return
        
    print(f"Starting reset for stations: {valid_stations}")
    
    # Start reset threads
    for station in valid_stations:
        thread = threading.Thread(target=reset_single_controller, args=(station,))
        threads.append(thread)
        thread.start()
    
    # Wait for all resets to complete
    for thread in threads:
        thread.join()
    
    # Standard wait time after reset
    time.sleep(10)

def axis_name(station):
    """Get list of available axes for a specific station."""
    # Get controller for the station
    controller = get_station_controller(station)
    if not controller:
        print(f"No controller found for station {station}")
        return []

    non_virtual_axes = []
    connected_axes = {}

    number_of_axes = controller.runtime.parameters.axes.count
    print(f"Number of axes for station {station}: {number_of_axes}")

    if number_of_axes <= 12:
        for axis_index in range(0, 11):
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
            
            result = controller.runtime.status.get_status_items(status_item_configuration)
            axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
            if (axis_status & 1 << 13) > 0:
                axis_name = controller.runtime.parameters.axes[axis_index].identification.axisname.value
                connected_axes[axis_name] = axis_index
                non_virtual_axes.append(axis_name)
    
    print(f'Axes present for station {station}: {non_virtual_axes}')
    return non_virtual_axes

def multiple_controllers():
    global controller_ST01, controller_ST02, controller_ST03
    try:
        controller_ST01 = a1.Controller.connect(host='192.168.1.15')
        controller_ST02 = a1.Controller.connect(host='192.168.1.16')
        controller_ST03 = a1.Controller.connect(host='192.168.1.17')
        controller_ST01_name = controller_ST01.name
        controller_ST02_name = controller_ST02.name
        controller_ST03_name = controller_ST03.name
        print(f'Controller For Station 1: {controller_ST01_name}')
        print(f'Controller For Station 2: {controller_ST02_name}')
        print(f'Controller For Station 3: {controller_ST03_name}')
        controller_ST01.start()
        controller_ST02.start()
        controller_ST03.start()
        running_ST01 = controller_ST01.is_running
        running_ST02 = controller_ST02.is_running
        running_ST03 = controller_ST03.is_running
        print(f'Running Station 1: {running_ST01}')
        print(f'Running Station 2: {running_ST02}')
        print(f'Running Station 3: {running_ST03}')
    except:
        messagebox.showerror('No Device', 'No Devices Present. Check Connections.')
    
    print(f'Station 1 Number of Axes: {controller_ST01.runtime.parameters.axes.count}')
    print(f'Station 2 Number of Axes: {controller_ST02.runtime.parameters.axes.count}')
    print(f'Station 3 Number of Axes: {controller_ST03.runtime.parameters.axes.count}') 

def single_controller():
    global controller
    try:
        controller_ST01 = a1.Controller.connect(host='192.168.1.16')
        controller_ST01_name = controller_ST01.name
        print(f'Controller For Station 1: {controller_ST01_name}')
        controller_ST01.start()
        running_ST01 = controller_ST01.is_running
        print(f'Running Station 1: {running_ST01}')
    except:
        messagebox.showerror('No Device', 'No Devices Present. Check Connections.')

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

def serial_com():
    num_readings = 5
    dwell = 1
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        print(f"Port: {port.device}, Description: {port.description}")
    USB_port = None
    RS232_port = None
    for p in ports:
        if "Silicon Labs CP210x" in p.description:
            USB_port = p.device  # p.device contains the COM port, e.g., 'COM4'
            break  # Stop after finding the first match
        if "Communications Port (COM1)" in p.description:
            RS232_port = p.device
    print(f'RS232 Port: {RS232_port}')
    try:
        reading = 1
        Xvalues = []
        Yvalues = []
        
        try:
            temp_ser = serial.Serial(RS232_port)
            temp_ser.close()
        except serial.SerialException as e:
            print(f'Error: {e}')
            try:
                temp_ser.close()
            except:
                pass
        #Start a loop that takes a collimator reading for the specified number of readings.
        while reading <= num_readings:
            reading = reading+1
            # Open serial port
            ser = serial.Serial(RS232_port, baudrate=19200, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=dwell)  # Adjust 'COM1' to your COM port
        
            # Write command to the serial port
            ser.write(b'r\x0D')
        
            # Read response from the serial port
            data = ser.readline().decode().strip()
            response = data.split()
            if response:
                #Take data from autocollimator through RS232 port
                measurement_type = response[0]

                status = response[1]
                vx = float(response[2])
                vy = float(response[3])

                Xvalues.append(vx)
                Yvalues.append(vy)
            else:
                #Display messagebox for no data condition, close the serial port, and end the program.
                messagebox.showerror('Collimator Error', 'No Signal From Autocollimator.')
                root.destroy()
                ser.close()
                break
            
            ser.close()
        
        if len(Xvalues) == num_readings:
            #Average X and Y values as a returnable variable
            Xavg = np.average(Xvalues, axis=None)
            Yavg = np.average(Yvalues, axis=None)
            Xavg = str(round(Xavg,3))
            Yavg = str(round(Yavg,3))
        else:
            pass

    except serial.SerialException as e:
        messagebox.showerror("Serial communication error:", e)
        root.destroy()

    except KeyboardInterrupt:
        messagebox.showerror("Stop Issued","Stop Issued. Ending Program")
        root.destroy()

    if 'ser' in locals():
        ser.close()
    
    return(Xavg,Yavg)

def connect_to_stations():
    global stations, test_axes
    num_stations = 3
    serial_number = '100000'
    program_id = id(threading.current_thread())  # Unique identifier for this program instance
    
    # Try to allocate stations
    stations = allocate_stations(num_stations, program_id)
    if stations is None:
        print("Not enough free stations available.")
        return False

    print(f"Successfully allocated stations {stations} for serial number {serial_number}")
    
    # Create controller objects for each allocated station
    successful_connections = []
    failed_stations = []
    
    try:
        # Try to acquire the lock with a timeout of 5 seconds
        if not station_lock.acquire(timeout=5):
            print("Could not acquire station lock - timeout")
            return False
            
        for station in stations:
            station_name = station_states[station]["axis_name"]
            
            if station_name in station_dict:
                try:
                    ip_address = station_dict[station_name]
                    try:
                        controller = a1.Controller.connect(host=ip_address)
                    except Exception as e:
                        controller = a1.Controller.connect()

                    controller.start()
                    # Store controller in station_states
                    station_states[station].update({
                        "status": "in-use",
                        "controllers": controller,
                        "program_id": program_id,
                        "serial_number": serial_number
                    })
                    successful_connections.append(station)
                    test_axes.append(station_name)
                    print(f"Successfully connected to {station_name} at {ip_address}")
                except Exception as e:
                    print(f"Failed to connect to {station_name}: {str(e)}")
                    # Mark this station as failed but continue trying others
                    failed_stations.append(station)
                    # Reset the station state back to free for this failed station
                    station_states[station].update({
                        "status": "free",
                        "controllers": None,
                        "program_id": None,
                        "serial_number": None
                    })
                    continue
            else:
                print(f"Station {station_name} not found in station_dict")  # Debug print
                failed_stations.append(station)
                # Reset the station state back to free for this failed station
                station_states[station].update({
                    "status": "free",
                    "controllers": None,
                    "program_id": None,
                    "serial_number": None
                })
        
        # Check if we have any successful connections
        if not successful_connections:
            print("No controllers could be connected. Releasing all allocated stations.")
            release_stations(stations)
            return False
        elif failed_stations:
            print(f"Successfully connected to {len(successful_connections)} stations. Failed connections: {[station_states[s]['axis_name'] for s in failed_stations]}")
        else:
            print(f"Successfully connected to all {len(successful_connections)} stations.")
    except Exception as e:
        print(f"Error in connect_to_stations: {str(e)}")
        return False
    finally:
        try:
            station_lock.release()
        except RuntimeError:
            pass

    print(f'Test Axes: {test_axes}')
    return True

def home_setup(controller, axis):
    
    home_setup = controller.runtime.parameters.axes[axis].homing.hometype.value
    print(f'Home Setup: {home_setup}')
    return home_setup

def home_station_thread(station):
    """Helper function to home a single station."""
    controller = get_station_controller(station)
   
    if not controller:
        print(f"No controller found for station {station}")
        return
    
    try:
        axis_name = station_states[station]["axis_name"]
        print(f'Axis Name: {axis_name}')
        print(f"Starting homing sequence for {axis_name}")
        
        # Verify controller is running
        if not controller.is_running:
            print(f"Controller for {axis_name} is not running")
            return

        # Enable the axis first
        controller.runtime.commands.motion.enable(axis_name)
        print(f"Enabled {axis_name}")
        
        # Wait for axis to be enabled
        time.sleep(1)
        
        # Start homing
        print(f"Sending home command to {axis_name}")
        controller.runtime.commands.motion.home(axis_name)
        
        # Wait for homing to complete with timeout
        timeout = time.time() + 30  # 30 second timeout
            
    except Exception as e:
        print(f"Error homing {axis_name}: {str(e)}")
        # Check final status

def home_stations():
    """Home all stations simultaneously using threads."""
    global stations, test_axes
    threads = []

    print(f"Test Axes: {test_axes}")
    for station in stations:
        axis_name = station_states[station]["axis_name"]
        controller = get_station_controller(station)
        params(controller, axis_name, home_offset=-12, current_clamp=5, limit='electrical on')
    reset_controllers()
    print(f"Starting homing for stations: {stations}")  # Debug print
    
    # Create a thread for each station
    for station in stations:
        thread = threading.Thread(target=home_station_thread, args=(station,))
        threads.append(thread)
        thread.start()
    
    # Wait for all homing operations to complete
    for thread in threads:
        thread.join()
    
    print("All stations have completed homing")

def quick_connect():
    global controller, non_virtual_axes, connected_axes

    controller = a1.Controller.connect()
    controller.start()

    return controller

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
    return controller    #messagebox.showerror('No Device', 'No Devices Present. Check Connections.')

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
    

def motor_type(axis):
    # Motor type mapping
    motor_type_map = {
        0: "ACBrushlessLinear",
        1: "ACBrushlessRotary", 
        2: "DCBrush",
        3: "StepperMotor"
    }
    
    for axis in test_axes:
        controller = get_station_controller(axis)
        motor_type_value = controller.runtime.parameters.axes[axis].motor.motortype.value
        commutation = controller.runtime.parameters.axes[axis].motor.commutationinitializationsetup.value
        
        # Convert numeric value to integer and get description
        motor_type_int = int(motor_type_value)
        motor_type_description = motor_type_map.get(motor_type_int, f"Unknown motor type ({motor_type_int})")
        
        print(f'Motor Type: {motor_type_description}')
        print('Commutation: ', commutation)
        

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

def data_config(n: int, freq: a1.DataCollectionFrequency, axis: int) -> a1.DataCollectionConfiguration:
    """
    Data configurations. These are how to configure data collection parameters
    """
    # Create a data collection configuration with sample count and frequency
    data_config = a1.DataCollectionConfiguration(n, freq)

    # Add items to collect data on the entire system
    data_config.system.add(a1.SystemDataSignal.DataCollectionSampleTime)

    # Add items to collect data on the specified axis
    data_config.axis.add(a1.AxisDataSignal.DriveStatus, axis)
    data_config.axis.add(a1.AxisDataSignal.AxisFault, axis)
    data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, axis)
    data_config.axis.add(a1.AxisDataSignal.PositionFeedback, axis)
    data_config.axis.add(a1.AxisDataSignal.CurrentCommand, axis)
    data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)
    data_config.axis.add(a1.AxisDataSignal.VelocityCommand, axis)

    return data_config

def validate_halls(axis, hall_states, hall_encoder_positions):
    controller = get_station_controller(axis)
    hall_dict = {
        0: "001",
        60: "011",
        120: "010",
        180: "110",
        240: "100",
        300: "101",
        }
    sequence = []
    # Validate State at each Angle
    for electrical_angle, hall_state in hall_states[axis].items():
        if hall_state == hall_dict[electrical_angle]:
            sequence.append(hall_state)
        else:
            print(f"Hall state mismatch on axis {axis} at angle {electrical_angle}: {hall_state} != {hall_dict[electrical_angle]}")
    
    # Validate Encoder Direction
    start_pos = hall_encoder_positions[axis][0]
    end_pos = hall_encoder_positions[axis][300]
    encoder_direction = "positive" if end_pos > start_pos else "negative"
    if encoder_direction == "negative":
        print(f"Encoder direction mismatch on axis {axis}. Please check encoder wiring.")

    # Validate Hall Sequence
    if encoder_direction == "positive":
        expected_order_cw = ["001", "011", "010", "110", "100", "101"]
        if sequence == expected_order_cw:
            print(f"Hall sequence is correct on axis {axis}")
        else:
            print(f"Hall sequence is incorrect on axis {axis}")

    # Check Commutation Offset
    for i, e in hall_states[axis].items():
        if e != hall_dict[i]:
            correct_angle = hall_dict[e]
            commutation_offset = abs(i - correct_angle)
            print(f"Commutation offset on axis {axis} is {commutation_offset} degrees.")
            break
        
def populate(axis, results):
    """
    Populate the hall sensor and primary feedback data structures based on the results of a data collection run.
    """
    sample_rate = 1000
    # Initialize dictionary entries for this axis with nested structure
    if axis not in hall_states:
        hall_states[axis] = {}
    if axis not in hall_encoder_positions:
        hall_encoder_positions[axis] = {}
    
    # Initialize other lists
    hall_a[axis] = []
    hall_b[axis] = []
    hall_c[axis] = []
    ccw_fault[axis] = []
    cw_fault[axis] = []
    pos_error_fault[axis] = []
    over_current_fault[axis] = []
    
    # Define check points (in seconds) and corresponding electrical angles
    check_points = [1.5, 4.5, 7.5, 10.5, 13.5, 16.5]
    electrical_angles = [0, 60, 120, 180, 240, 300]  # degrees
    
    # Get the data
    halls = results.axis.get(a1.AxisDataSignal.DriveStatus, axis).points
    pri_fbk = results.axis.get(a1.AxisDataSignal.PrimaryFeedback, axis).points

    time_array = np.array(results.system.get(a1.SystemDataSignal.DataCollectionSampleTime).points)
    time_array -= time_array[0]
    time_array *= .001 #msec to sec
    time_array = time_array.tolist()
    
    for i, t in enumerate(time_array):
        time_array[i] = i/sample_rate
        
        # Check if we're at one of our target times
        check_time = check_points[len(hall_states[axis].keys())] if len(hall_states[axis].keys()) < len(check_points) else None
        if check_time and abs(time_array[i] - check_time) < (1/sample_rate):
            hall_a_data = 1 if ((int(halls[i]) & a1.DriveStatus.HallAInput.value) > 0) else 0
            hall_b_data = 1 if ((int(halls[i]) & a1.DriveStatus.HallBInput.value) > 0) else 0
            hall_c_data = 1 if ((int(halls[i]) & a1.DriveStatus.HallCInput.value) > 0) else 0
            hall_state = f"{hall_a_data}{hall_b_data}{hall_c_data}"
            current_angle = electrical_angles[len(hall_states[axis].keys())]
            
            # Store values with angle as key
            hall_states[axis][current_angle] = hall_state
            hall_encoder_positions[axis][current_angle] = pri_fbk[i]
    
    validate_halls(axis, hall_states, hall_encoder_positions)   
    
def halls(axis):
    controller = get_station_controller(axis)
    sample_rate = 1000
    test_time = 22
    n = int(sample_rate * test_time)
    freq = a1.DataCollectionFrequency.Frequency1kHz
        
    angle = 0
    current_threshold = controller.runtime.parameters.axes[axis].protection.averagecurrentthreshold.value
    current = current_threshold / 2
    
    config = data_config(n, freq, axis)

    controller.runtime.commands.motion.enable([axis])
    
    controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, config)
    
    while angle < 350:
        controller.runtime.commands.servo_loop_tuning.tuningsetmotorangle(axis, current, angle)
        angle += 60
        time.sleep(3)
    
    time.sleep(5)
        
    controller.runtime.data_collection.stop()
            
    results = controller.runtime.data_collection.get_results(config, n)
    
    controller.runtime.commands.motion.abort([axis])
    controller.runtime.commands.motion.enable([axis])
    populate(axis, results)

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
        # Store the axis_faults in the faults dictionary with the axis as the key
        faults[axis] = axis_faults  # Store the result in the dictionary with the axis as the key
        
    return faults

def upload_mcd(station):
    print(f'Uploading MCD for {station}')
    controller = get_station_controller(station)
    print(f'Controller: {controller}')
    mdk_path = r'C:\Users\tbates\Documents\Automation1\PRO165SL.mcd'
    controller.upload_mcd_to_controller(mdk_path, should_include_files=True, should_include_configuration=True, erase_controller=False)
    print(f'MCD uploaded for {station}')

    reset_controllers()

def frequency_response(station):
    controller = a1.Controller.connect()
    controller.runtime.commands.execute('AppFrequencyResponseTriggerMultisinePlus(X, "test.fr", 20, 2000, 250, 5, TuningMeasurementType.ServoOpenLoop, 5, 1)',1)

           
def main(test=None):
    """Main function to load JSON and get parameters for an axis."""
    print(f"Starting main with test={test}")  # Debug print
    
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
    if test == 'Single Controller':
        single_controller()
    if test == 'Connect to Stations':
        print("Initiating station connection...")  # Debug print
        success = connect_to_stations()
        if success:
            for station in stations:
                axis_name(station)
            print("Connection successful, proceeding to home stations...")  # Debug print
            home_stations()
        else:
            print("Failed to connect to stations")  # Debug print
    if test == 'Serial':
        xavg, yavg = serial_com()
        print(f'Xavg: {xavg}, Yavg: {yavg}')
    if test == 'Upload MCD':
        success = connect_to_stations()
        if success:
            for station in stations:
                if station == 'ST03':
                    upload_mcd(station)
    if test == 'Motor Type':
        success = connect_to_stations()
        if success:
            for station in stations:
                motor_type(station)
    if test == 'Home Setup':
        controller = quick_connect()
        if controller:
            station = 'ST01'
            home_setup(controller, station)
    
    if test == 'Halls':
        success = connect_to_stations()
        if success:
            for station in stations:
                if station == 'ST03':
                    halls('ST03')

# When running the script
if __name__ == "__main__":
    print("Starting program...")  # Debug print
    main(test='Home Setup')
    print("Program completed")  # Debug print
