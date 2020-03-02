"""
X-Plane Socket Forwarding
"""

import socket
import struct


class XPlaneDataType:
    """
    Data Reference type holder for which data formats go with different parameters
    """
    __slots__ = ('name', 'dataref_id', 'dataref_type', 'dataref_num', 'units')
    
    def __init__(self, name, dataref_id, dataref_type, dataref_num, units):
        """
        Initializes the data type class with the provided ID and format
        """
        self.name = name
        self.dataref_id = dataref_id
        self.dataref_type = dataref_type
        self.dataref_num = dataref_num
        self.units = units

    @staticmethod
    def get_xp_data_type_list():
        type_list = list()

        type_list.append(XPlaneDataType(
            name='Pitch',
            dataref_id=17,
            dataref_type='f',
            dataref_num=0,
            units='deg'))

        type_list.append(XPlaneDataType(
            name='Roll',
            dataref_id=17,
            dataref_type='f',
            dataref_num=1,
            units='deg'))

        type_list.append(XPlaneDataType(
            name='HeadingTrue',
            dataref_id=17,
            dataref_type='f',
            dataref_num=2,
            units='deg'))

        type_list.append(XPlaneDataType(
            name='HeadingMag',
            dataref_id=17,
            dataref_type='f',
            dataref_num=3,
            units='deg'))

        type_list.append(XPlaneDataType(
            name='Latitude',
            dataref_id=20,
            dataref_type='f',
            dataref_num=0,
            units='deg'))

        type_list.append(XPlaneDataType(
            name='Longitude',
            dataref_id=20,
            dataref_type='f',
            dataref_num=1,
            units='deg'))

        type_list.append(XPlaneDataType(
            name='AltitudeMSL',
            dataref_id=20,
            dataref_type='f',
            dataref_num=2,
            units='ft'))

        type_list.append(XPlaneDataType(
            name='AltitudeAGL',
            dataref_id=20,
            dataref_type='f',
            dataref_num=3,
            units='ft'))

        type_list.append(XPlaneDataType(
            name='RPM',
            dataref_id=37,
            dataref_type='f',
            dataref_num=0,
            units='rpm'))

        type_list.append(XPlaneDataType(
            name='EGT',
            dataref_id=47,
            dataref_type='f',
            dataref_num=0,
            units='degC'))

        type_list.append(XPlaneDataType(
            name='EGT',
            dataref_id=48,
            dataref_type='f',
            dataref_num=0,
            units='degC'))

        type_list.append(XPlaneDataType(
            name='OilPressure',
            dataref_id=49,
            dataref_type='f',
            dataref_num=0,
            units='psi'))

        type_list.append(XPlaneDataType(
            name='OilTemperature',
            dataref_id=50,
            dataref_type='f',
            dataref_num=0,
            units='degC'))

        type_list.append(XPlaneDataType(
            name='AirspeedIndicated',
            dataref_id=3,
            dataref_type='f',
            dataref_num=0,
            units='kts'))

        type_list.append(XPlaneDataType(
            name='Groundspeed',
            dataref_id=3,
            dataref_type='f',
            dataref_num=2,
            units='kts'))

        return type_list

    @staticmethod
    def get_type_for_name(name, type_list):
        for t in type_list:
            if name == t.name:
                return t
        return None


class XPlaneDataRef:
    """
    Class to hold X-Plane 11 Data Reference Types
    """
    __slots__ = ('xp_type', 'data')

    def __init__(self, xp_type, data):
        self.xp_type = xp_type
        self.data = data


class XPlaneDataReceiver:
    """
    Class to facilitate connecting and parsing XPlane Data References
    """

    def __init__(self, listen_address=('127.0.0.1', 49009), little_endian=True):
        """
        Creates and opens the socket to receive data from X-Plane
        """
        # Setup the socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Connect and save the socket
        sock.bind(listen_address)
        self.sock = sock

        # Create the dataref dictionary
        self.dataref_dict = dict()
        self.dataref_type_list = XPlaneDataType.get_xp_data_type_list()

        # Determine the endian-ness string for the incoming bytes
        self.endian_str = '<' if little_endian else '>'
    
    def read_xplane_data(self):
        """
        Attempts to read data from the X-Plane socket and parses into the
        local dictionary
        """
        socket_error_string = None

        # Receive data from the socket
        try:
            data, from_addr = self.sock.recvfrom(4096)
        except socket.error as e:
            socket_error_string = str(e)

        # Throw warning if there has been a socket error
        if socket_error_string is not None:
            raise XPlaneDataError('socket error - {:s}'.format(socket_error_string))

        # Setup the header parameters
        header_len = 5
        header_param = 'DATA'

        # Create the dataref parameters
        dataref_len = 36
        dataref_byte_num = 4

        # Ensure that the constants are set up properly
        assert len(header_param) <= header_len

        # Determine if the received data is valid
        if len(data) <= header_len:
            return
        elif (len(data) - header_len) % dataref_len != 0:
            return
        elif data[0:len(header_param)].decode('utf-8') != 'DATA':
            return

        # Extract the dataref parameters
        datarefs = data[header_len:]

        # Create an incrementer to step through the bytes
        i = 0

        # Loop through all the bytes
        while i * dataref_len < len(datarefs):
            # Define start/end indexes
            start_index = i * dataref_len
            end_index = start_index + dataref_len - 1

            # Run some assertions
            assert start_index < len(datarefs)
            assert end_index < len(datarefs)

            # Extract the current dataref bytes
            dataref = datarefs[start_index:end_index]

            # Extract and parse the dataref id number
            id_bytes = dataref[0:dataref_byte_num]
            dataref_id = struct.unpack(self.endian_str + 'I', id_bytes)[0]

            # Create constants for each of the dataref values
            dataref_bytes = dataref[dataref_byte_num:]
            dataref_data = []

            # Iterate through each of the dataref parameters, parse, and append to the data
            for j in range(len(dataref_bytes) // dataref_byte_num):
                start_index_d = (j + 1) * dataref_byte_num
                end_index_d = (j + 2) * dataref_byte_num
                
                data_item_b = dataref[start_index_d:end_index_d]
                data_item_val = struct.unpack(self.endian_str + 'f', data_item_b)[0]
                
                dataref_data.append(data_item_val)

            # Append value to dictionary
            self.dataref_dict[dataref_id] = dataref_data

            # Increment the iterator
            i += 1

        return True
    
    def close(self):
        self.sock.close()


class XPlaneDataError(BaseException):
    """
    XPlaneDataError

    Error class to hold information regarding X-Plane data parser errors
    """
    __slots__ = ('what',)

    def __init__(self, error_string):
        self.what = error_string

    def __str__(self):
        return self.what
