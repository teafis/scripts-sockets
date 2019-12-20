"""
Sends sample packets to the requested IP addresses for spoofing data parameters
"""

import efis_packet_format as efis
from forward_ip_addresses import UDP_IPS, UDP_PORT

import time
import socket

for ip in UDP_IPS:
    print("UDP target IP:", ip)
print("UDP target port:", UDP_PORT)

signal_list = efis.SignalList(efis.signal_list_file)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP

analog_packet_names = [
    'engine_rpm',
    'oil_pressure',
    'oil_temperature',
    'speed_ias',
    'altitude_msl',
    'att_pitch',
    'att_roll']

analog_packets = [
    efis.AnalogPacket.from_signal_def(
        efis.PC_1_DEV_ID,
        signal_list.get_definition(name))
    for name in analog_packet_names]

analog_min_vals = [
    -200,
    -20,
    -50,
    0,
    -1000,
    -30,
    -60]
analog_max_vals = [
    3200,
    450,
    200,
    270,
    18000,
    30,
    60]
analog_incrementor_vals = [
    10,
    1,
    1,
    0.1,
    1,
    0.1,
    0.1]
analog_vals = [
    0,
    0,
    0,
    0,
    0,
    0,
    0]

assert len(analog_packets) == len(analog_vals)
assert len(analog_packets) == len(analog_min_vals)
assert len(analog_packets) == len(analog_max_vals)
assert len(analog_packets) == len(analog_incrementor_vals)

try:
    while True:
        for i in range(len(analog_packets)):
            packet = analog_packets[i].create_packet_with_data(analog_vals[i])

            for ip in UDP_IPS:
                sock.sendto(packet, (ip, UDP_PORT))

            if analog_vals[i] > analog_max_vals[i] or analog_vals[i] < analog_min_vals[i]:
                analog_incrementor_vals[i] *= -1
            analog_vals[i] += analog_incrementor_vals[i]

        time.sleep(0.01)


except KeyboardInterrupt:
    pass

sock.close()


