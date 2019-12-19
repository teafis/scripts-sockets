"""
Defines and creates EFIS packets for sending
"""

from datetime import datetime

from enum import Enum

import struct

signal_list_file = 'signals/signal_list.csv'

PC_1_DEV_ID = 30


class SignalList:
    def __init__(self, signal_file):
        # Create the definition list
        self.def_list = dict()

        # Open and read all data
        with open(signal_file, 'r') as f:
            data = f.read()

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
                    ValueError('Cannot have to signals with the same definition in the signal list')
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

                    if s1.cat_id == s2.cat_id and s1.sig_id == s2.sig_id:
                        ValueError('Cannot have two signals with the same category and signal ids')

    def get_definition(self, name):
        return self.def_list[name]


class SignalDefinition:
    def __init__(self, cat_id, sig_id, name, unit, sig_type, timeout_msec):
        self.cat_id = cat_id
        self.sig_id = sig_id
        self.name = name
        self.unit = unit
        self.sig_type = sig_type
        self.timeout_msec = timeout_msec

    @staticmethod
    def from_csv_line(line):
        # # CategoryID	SignalID	Name	Units	Type	TimeoutMsec
        words = [l.strip() for l in line.split(',')]

        cat_id = int(words[0])
        sig_id = int(words[1])
        name = words[2]
        unit = words[3]
        sig_type = words[4]
        timeout_msec = int(words[5])

        if sig_type != 'double':
            raise ValueError('Signals of type other than "double" not yet supported')

        return SignalDefinition(cat_id, sig_id, name, unit, sig_type, timeout_msec)


def create_network_header(dev_from, category, signal_id, ts=None):
    if ts is None:
        dt = datetime.utcnow()
        timestamp_ms = dt.microsecond
    else:
        assert False
        
    return struct.pack('!BIBB', dev_from, timestamp_ms, category, signal_id)


def create_analog_data(data):
    return struct.pack('!dB', float(data), 0)


class AnalogPacketDefinition:
    __slots__ = ('dev_from', 'dev_to', 'category', 'signal_id')

    def __init__(self, dev_from, category, signal_id):
        self.dev_from = dev_from
        self.category = category
        self.signal_id = signal_id

    @staticmethod
    def from_signal_def(from_dev, s_def):
        return AnalogPacketDefinition(from_dev, s_def.cat_id, s_def.sig_id)

    def create_packet_with_data(self, data):
        header = create_network_header(
            dev_from=self.dev_from,
            category=self.category,
            signal_id=self.signal_id)
        analog_part = create_analog_data(data=data)

        return header + analog_part
