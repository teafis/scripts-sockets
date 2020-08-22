"""
Forwards data from X-Plane to any requested IP address and port
"""

import socket
import time

import math

import efis_packet_format as efis
import xp_udp_dataparser as xpdata
from forward_ip_addresses import UDP_IPS, UDP_PORT

for ip in UDP_IPS:
    print("UDP target IP:", ip)
print("UDP target port:", UDP_PORT)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP

xp_udp = xpdata.XPlaneDataReceiver()
signal_list = efis.SignalList(efis.signal_list_file)


def map_xplane_name_to_signal(xplane_name, signal_name):
    xplane_def = xpdata.XPlaneDataType.get_type_for_name(xplane_name, xp_udp.dataref_type_list)
    signal_def = efis.AnalogPacket.from_signal_def(efis.PC_1_DEV_ID, signal_list.get_definition(signal_name))
    return xplane_def, signal_def


xp_to_efis_links = [
    map_xplane_name_to_signal('RPM', 'engine_rpm'),
    map_xplane_name_to_signal('OilPressure', 'oil_pressure'),
    map_xplane_name_to_signal('OilTemperature', 'oil_temperature'),
    map_xplane_name_to_signal('Latitude', 'gps_latitude'),
    map_xplane_name_to_signal('Longitude', 'gps_longitude'),
    map_xplane_name_to_signal('AltitudeMSL', 'altitude_msl'),
    map_xplane_name_to_signal('AirspeedIndicated', 'speed_ias'),
    map_xplane_name_to_signal('Groundspeed', 'speed_gs'),
    map_xplane_name_to_signal('Pitch', 'att_pitch'),
    map_xplane_name_to_signal('Roll', 'att_roll'),
    map_xplane_name_to_signal('HeadingTrue', 'heading_true'),
    map_xplane_name_to_signal('HeadingMag', 'heading_mag')]


try:
    while True:
        try:
            xp_udp.read_xplane_data()
        except xpdata.XPlaneDataError as e:
            print('Error - skipping - {:s}'.format(str(e)))
            continue

        for link in xp_to_efis_links:
            dataref_id = link[0].dataref_id

            if dataref_id not in xp_udp.dataref_dict:
                continue

            dataref_num = link[0].dataref_num

            xp_dataref = xp_udp.dataref_dict[dataref_id]
            data = xp_dataref[dataref_num]

            if link[0].name == 'HeadingTrue' or link[0].name == 'HeadingMag':
                if data > 180:
                    data = data - 360

                if data > 180:
                    data = 180
                elif data < -180:
                    data = -180

            packet = link[1].create_packet_with_data(data_input=data)

            for ip in UDP_IPS:
                sock.sendto(packet, (ip, UDP_PORT))

        time.sleep(0.01)

except KeyboardInterrupt:
    pass

sock.close()

