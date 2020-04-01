"""
Defines and creates EFIS packets for sending
"""

from datetime import datetime
from enum import Enum
import io
import struct


# Default signal list definitions
signal_list_file = 'signals/signal_list.csv'

# Device ID definitions
PC_1_DEV_ID = 30
PC_2_DEV_ID = 31


class SignalList:
    """
    Class to maintain signals present within a signal list file
    """
    def __init__(self, signal_file):
        """
        Reads the input signal list file into the local dictionary
        :param signal_file:
        :type  signal_file: str or io.TextIOBase
        """
        # Create the definition list
        self.def_list = dict()

        # Open and read all data from either the filename or the handle provided
        if type(signal_file) is str:
            with open(signal_file, 'r') as f:
                data = f.read()
        elif type(signal_file) is io.TextIOBase:
            data = signal_file.read()
        else:
            raise ValueError('signal_file must be either a filename or a readable stream')

        # Set a boolean to toggle the first line
        first_line = True

        # Iterate over all parameters in the signal list
        for line in [l for l in data.splitlines()]:
            # Ignore comment lines
            if list(line)[0] == '#':
                continue

            # Set the version number from the first line
            if first_line:
                self.version = int(line.replace(',', ''))
                first_line = False
            # Otherwise, read in the signals
            else:
                s_def = SignalDefinition.from_csv_line(line)

                if s_def.name in self.def_list:
                    raise ValueError('Cannot have to signals with the same definition in the signal list')
                else:
                    self.def_list[s_def.name] = s_def

        # Run another check to make sure that no signals have duplicate ids
        for key_i in self.def_list.keys():
            for key_j in self.def_list.keys():
                if key_i == key_j:
                    continue
                else:
                    s1 = self.def_list[key_i]
                    s2 = self.def_list[key_j]

                    if s1.cat_id == s2.cat_id and s1.sub_id == s2.sub_id:
                        raise ValueError('Cannot have two signals with the same category and signal ids')

    def get_definition(self, name):
        """
        Provides the signal for a given signal name in the dictionary. None if not in dictionary
        :param name: signal definition to get from the dictionary
        :type  name: str
        :return: signal definition for the signal if in the dictionary; otherwise None
        :rtype: SignalDefinition or None
        """
        if name in self.def_list:
            return self.def_list[name]
        else:
            return None


class SignalDefinition:
    """
    Class to maintain the definition for a signal type
    """

    def __init__(self, cat_id, sub_id, name, unit, sig_type, timeout_msec):
        """
        Creates a signal definition for the provided input parameters
        :param cat_id: the category ID for the signal
        :type  cat_id: int
        :param sub_id: the signal ID for the signal
        :type  sub_id: int
        :param unit: the unit assiciated with the signal
        :type  unit: str
        :param sig_type: the signal type
        :type  sig_type: str
        :param timeout_msec: the number of milliseconds until timeout for the signal
        :type  timeout_msec: int
        """
        self.cat_id = cat_id
        self.sub_id = sub_id
        self.name = name
        self.unit = unit
        self.sig_type = sig_type
        self.timeout_msec = timeout_msec

    @staticmethod
    def from_csv_line(line):
        """
        Provides a signal definition from a signle comma-separated line of the signal list, in the form
          CategoryID,SubID,Name,Units,Type,TimeoutMsec
        :param line: the line to extract the signal definition from
        :type  line: str
        :return: the signal definition for the values found in the line
        :rtype: SignalDefinition
        """
        # Split the input line by commas
        words = [l.strip() for l in line.split(',')]

        # Ensure that there is the expected number of parameters
        if len(words) != 7:
            raise ValueError('Invalid number of parameters found in the line, expecting 6, got {:d}'.format(len(words)))

        # Extract the signal parameters
        cat_id = int(words[0])
        sub_id = int(words[1])
        name = words[2]
        unit = words[3]
        sig_type = words[4]
        timeout_msec = int(words[5])

        if words[6] == 'semi2deg':
            resolution = 180.0 / 2**31
        else:
            resolution = float(words[6])

        # Check that the signal type is the value expected
        if sig_type != 'fixed':
            raise ValueError('Signals of type other than "double" not yet supported')

        # Create and return the signal definition
        return AnalogSignalDefinition(
            cat_id=cat_id,
            sub_id=sub_id,
            name=name,
            unit=unit,
            sig_type=sig_type,
            timeout_msec=timeout_msec,
            resolution=resolution)


class AnalogSignalDefinition(SignalDefinition):
    """
    Class to maintain the definition for an analog signal type
    """
    def __init__(self, cat_id, sub_id, name, unit, sig_type, timeout_msec, resolution):
        """
        Creates a signal definition for the provided input parameters
        :param cat_id: the category ID for the signal
        :type  cat_id: int
        :param sub_id: the signal ID for the signal
        :type  sub_id: int
        :param unit: the unit assiciated with the signal
        :type  unit: str
        :param sig_type: the signal type
        :type  sig_type: str
        :param timeout_msec: the number of milliseconds until timeout for the signal
        :type  timeout_msec: int
        :param resolution: the resolution to multiply network data by to get the engineering data
        :type resolution: float
        """
        super().__init__(cat_id, sub_id, name, unit, sig_type, timeout_msec)
        self.resolution = resolution


class GenericPacket:
    """
    A generic packet class to maintain common information for all packets
    """
    _expected_type = None

    def __init__(self, dev_from_id, cat_id, sub_id, signal_def):
        """
        Initializes the packet with the provided information
        :param dev_from_id: the ID of the sending device
        :type  dev_from_id: int
        :param cat_id: the category ID for the packet
        :type  cat_id: int
        :param sub_id: the signal ID for the packet
        :type  sub_id: int
        :param signal_def: the signal definition for the packet parameter
        :type signal_def: SignalDefinition
        """
        self.dev_from_id = dev_from_id
        self.cat_id = cat_id
        self.sub_id = sub_id
        self.signal_def = signal_def

    @classmethod
    def from_signal_def(cls, dev_from_id, signal_def):
        """
        Initializes a packet of the given class based on a signal definition
        :param dev_from_id: the ID of the sending device
        :type  dev_from_id: int
        :param signal_def: the signal definition to use for the packet
        :type  signal_def: SignalDefinition
        """
        if cls._expected_type is not None and signal_def.sig_type != cls._expected_type:
            raise ValueError('Signal type {:s} does not match {:s} expected type {:s}'.format(
                signal_def.sig_type,
                type(cls).__name__,
                cls._expected_type))

        return cls(
            dev_from_id=dev_from_id,
            cat_id=signal_def.cat_id,
            sub_id=signal_def.sub_id,
            signal_def=signal_def)

    def _create_network_header(self, ts=None):
        """
        Creates a network header for the packet
        :param ts: optional parameter to manually define the timestamp. Uses UTC micros timestamp if None
        :type  ts: int or None
        :return: packed header bytes
        :rtype: bytes
        """
        # Determine the timestamp to use
        if ts is None:
            dt = datetime.utcnow()
            timestamp_ms = dt.microsecond
        else:
            raise NotImplementedError('Manual timestamp not yet supported')

        # Pack the information into network-order bytes
        return struct.pack(
            '!BIBB',
            self.dev_from_id,
            timestamp_ms,
            self.cat_id,
            self.sub_id)

    def _create_data_bytes(self, data_input):
        """
        Virtual packet to be used in child classes for creating data parameters
        :param data_input: the data to pack into the byte structure
        :type  data_input: float or int or bool
        :return: packed data bytes
        :rtype: bytes
        """
        raise NotImplementedError('_create_data must be defined in each packet type')

    def _calculate_checksum(self, data):
        """
        Calculates the checksum of the provided data bytes
        :param data: the data to calculate the checksum of
        :type  data: bytes
        :return: packed checksum bytes
        :rtype: bytes
        """
        return struct.pack('!B', 0)

    def create_packet_with_data(self, data_input):
        """
        Creates a network packet with the provided data to pack into the packet
        :param data_input: the data to pack into the byte structure
        :type  data_input: float or int or bool
        :return: total packet bytes
        :rtype: bytes
        """
        # Create the data bytes
        data_part = self._create_network_header() + self._create_data_bytes(data_input=data_input)

        # Pack data together with the checksum
        return data_part + self._calculate_checksum(data_part)


class AnalogPacket(GenericPacket):
    """
    Packet type for analog double values within packets
    """
    _expected_type = 'fixed'

    def _create_data_bytes(self, data_input):
        """
        Overridden _create_data_bytes function to pack double values
        :param data_input: double value to pack
        :type  data_input: float
        :return: packed data bytes
        :rtype: bytes
        """
        return struct.pack('!i', int(data_input / self.signal_def.resolution))
