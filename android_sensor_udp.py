"""
Parses Sensor JSON input into a network-compatible form

Utilizes the Termux API application to obtain sensor information
"""

import json
import queue
import signal
import socket
import struct
import subprocess
import sys
import threading
import time

import efis_packet_format as efis

class Sensor:
    """
    Sensor class to maintain the sensor name, ID, and current values,
    as well as whether the sensor has been updated since the last packet
    was constructed
    """

    # Slots data parameters for the structure
    __slots__ = ('sensor_id', 'name', 'vals', 'updated')

    # ID values associated with different sensor types
    # If a sensor is not in the dictionary, it will be added to the next value above the
    # maximum sensor currently in the list
    sensor_name_ids = {
        '3-axis Gyroscope': 1,
        '3-axis Accelerometer': 2,
        'Game Rotation Vector': 3
    }

    def __init__(self, name):
        """
        Init function to construct the sensor class with an input name
        :param name: The name of the sensor
        :type name: str
        """
        # Add the next-highest sensor ID to the dictionary if it is not already in the list
        if name not in self.sensor_name_ids:
            max_id_val = max([v for v in self.sensor_name_ids.values()])
            self.sensor_name_ids[name] = max_id_val + 1
            print('Adding {:s} = {:d}'.format(name, max_id_val + 1))

        # Extract the sensor ID and set the name
        self.sensor_id = self.sensor_name_ids[name]
        self.name = name

        # Initialize an empty list for values and set updated to False
        self.vals = list()
        self.updated = False

    def set_values(self, vals):
        """
        Sets the input values and marks the sensor as being updated
        :param vals: list of sensor values
        :type vals: list of float
        """
        # Set the values and mark updated as true
        self.vals = vals
        self.updated = True

    def construct_packet(self):
        """
        Constructs a data packet from the sensor and the last provided data parameters
        Data parameter are multiplied by 100 to give a resolution to 0.01 of the sensor units
        :return: a data packet of the form <ID><Updated><4-Byte Int Length>[<4-Byte Integer Sensor Value>] * Number of Values
        :rtype: bytes
        """
        # Set updated to False
        self.updated = False

        # Determine the data format string, consisting of the 4 bytes for header information (ID, updated, and integer count) and the integers
        data_format = '!BBB{:s}'.format(''.join(['i'] * len(self.vals)))

        # Perfom the multiplication to get the integers in the correct resolution
        data_vals = [int(v * 100) for v in self.vals]

        # Construct the data packet bytes
        return struct.pack(
            data_format,
            self.sensor_id,
            1 if self.updated else 0,
            len(data_vals),
            *data_vals)


def read_process_lines_to_queue(args_list, line_queue, stop_queue, return_code_queue):
    """
    Function to provide threading for reading input lines from an application
    :param args_list: arguments to open the subprocess
    :type args_list: list of str
    :param line_queue: queue that lines are put into after reading
    :type line_queue: queue.Queue
    :param stop_queue: queue that signals the thread to stop when not empty
    :type stop_queue: queue.Queue
    :param return_code_queue: queue to store the return code from the subprocess
    :type return_code_queue: queue.Queue
    :return: the process return code
    :rtype: int
    """
    # Create the process
    process = subprocess.Popen(args_list, stdout=subprocess.PIPE)
    rc = None

    while rc is None:
        # Read a line of output
        output = process.stdout.readline()

        # Check that the process is still valid
        # Otherwise, add the line to the queue
        if len(output) == 0 and process.poll() is not None:
            rc = process.poll()
        else:
            line_queue.put(output)

        # Check the stop queue
        if not stop_queue.empty():
            process.send_signal(signal.SIGINT)
            process.wait()
            rc = process.poll()
    
    # At end, return the process return code
    return_code_queue.put(rc)
    return rc


class ProcessSensorDecoder:
    """
    Wrapper class to surround a process to extract sensor information from stdout
    """
    args_list = ['termux-sensor', '-s', '3-axis Accelerometer, 3-axis Gyroscope, Rotation Vector', '-d', '100']

    def __init__(self):
        """
        Initializes the process JSON decoder with an initial process
        :param process: Process to parse stdout for useful JSON data
        :type process: subprocess.Process
        """
        # Set the input parameters
        #self.process = process
        self.json_str = None
        self.rc = None
        self.line_queue = queue.Queue()
        self.stop_queue = queue.Queue()
        self.return_code_queue = queue.Queue()

        # Create and start the thread
        self.process_thread = threading.Thread(
            target=read_process_lines_to_queue,
            args=[self.args_list, self.line_queue, self.stop_queue, self.return_code_queue])
        self.process_thread.start()

    def poll(self, sensors, line_limit_count=25):
        """
        Parses the process stdout to extract sensor JSON information
        :return: None if the process is still performing, return code if process has completed
        :rtype: None or int
        """
        # Return RC if process has already ended 
        if self.rc is not None:
            return self.rc

        # Define the line count
        line_count = 0

        # Loop while until line_queue is empty or the line count has been met
        while not self.line_queue.empty() and line_count < line_limit_count:
            # Read a line of output
            output = self.line_queue.get()
            line_count += 1

            # Decode the string and strip any newline characters
            decoded_str = output.decode('utf-8').strip('\n')

            # Check whether to create a new JSON string
            if decoded_str == '{':
                self.json_str = list()

            # Perform tasks if the JSON string list is valid
            if self.json_str is not None:
                # Appent the decoded string to the list
                self.json_str.append(decoded_str)

                # Detect if we have closed the JSON parameters
                if decoded_str == '}':
                    # Decode the JSON results and clear the string list
                    decoded_val = json.loads('\n'.join(self.json_str))
                    self.json_str = None

                    # Skip over sensor processing if sensors are None
                    if sensors is not None:
                        # Iterate over each sensor provided
                        for sensor_name, sensor_dict in decoded_val.items():
                            # If a sensor class is not yet provided, create one
                            if sensor_name not in sensors:
                                sensors[sensor_name] = Sensor(sensor_name)

                            # Extract the sensor parameter
                            sensor = sensors[sensor_name]

                            # Set the values to the decoded values in the sensor parameters
                            if 'values' in sensor_dict:
                                sensor.set_values(sensor_dict['values'])

        # Get the return code if ended
        # Otherwise, return None
        if self.process_thread.is_alive():
            return None
        else:
            self.stop()
            return self.rc
    
    def stop(self):
        """
        Requests a stop of the reading thread
        """
        self.stop_queue.put(None)
        self.process_thread.join()
        if self.return_code_queue.empty():
            self.rc = -1
        else:
            self.rc = self.return_code_queue.get()


def main(ip_addr):
    """
    Main function
    """
    # Create the dictionary to read in sensor values
    sensors = dict()
    
    # Read the signal list
    signal_list = efis.SignalList(efis.signal_list_file)
    
    # Extract the desired packet names
    analog_packet_names = [
        'att_pitch',
        'att_roll']

    analog_packets = [
        efis.AnalogPacketDefinition.from_signal_def(
            efis.PC_1_DEV_ID,
            signal_list.get_definition(name))
        for name in analog_packet_names]
    
    # Create a socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Print existing IDs
    print('Current IDs:')
    for s, i in Sensor.sensor_name_ids.items():
        print('  {:s} = {:d}'.format(s, i))

    process_decoder = None

    # Define an elapsed time function
    class ElapsedTime:
        def __init__(self):
            self.st = time.time()

        def tic(self):
            self.st = time.time()
        
        def toc(self):
            return time.time() - self.st

    # Elapsed Time
    et = ElapsedTime()

    # Loop for reading in sensor values and sending over the network
    try:
        # Create the sensor process decoder
        process_decoder = ProcessSensorDecoder()

        # Define an packet counter for printing
        packets_sent = 0

        # Loop the process decoder while parameters are available
        while process_decoder.poll(sensors) is None:
            # Determine which sensors have been updated
            updated_sensors = [v for v in sensors.values() if v.updated]

            # Print results if any have been updated
            if len(updated_sensors) > 0:
                data_val = bytes()
                for s in updated_sensors:
                    data_val += s.construct_packet()
                if len(data_val) > 0:
                    sock.sendto(data_val, (ip_addr, 5860))
                    packets_sent += 1
                if et.toc() > 1.0:
                    print('Delta Packets Sent: {:d}'.format(packets_sent))
                    et.tic()
                    packets_sent = 0
            
            # Send pitch/roll packets
            if 'Game Rotation Vector' in sensors:
                rotation_sensor = sensors['Game Rotation Vector']
                data_vals = [d *90.0 for d in rotation_sensor.vals[0:2]]
                sock.sendto(analog_packets[0].create_packet_with_data(data_vals[0]), (ip_addr, 7777))
                sock.sendto(analog_packets[1].create_packet_with_data(data_vals[1]), (ip_addr, 7777))
                print('Sent data {:.2f}, {:.2f}'.format(*data_vals))

            
    except KeyboardInterrupt:
        if process_decoder is not None:
            process_decoder.stop()

    # Print the resulting process code when complete
    rc_result = process_decoder.rc
    print('Finished with code {:d}'.format(rc_result))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        print('Sending to {:s}'.format(sys.argv[1]))
        main(sys.argv[1])
    else:
        print('No IP Address Provided')
