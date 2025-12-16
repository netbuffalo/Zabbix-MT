#0.0.0.0/0!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import re
import socket
import time
import argparse
import types
import struct

class ZabbixSender(object):
    def __init__(self, zabbix, port=10051, **kwargs):
        # zabbix host
        self.zabbix = zabbix
        # zabbix receiver port
        self.port = 10051
        # sender packets
        self.packets = {'request': 'sender data', 'data': []}
        self.parser = re.compile('(\{.*\})')

    def __str__(self):
        return json.dumps({'server': self.zabbix, 'port': self.port}, indent=4)

    def add_packet(self, host, key, val, clock=int(time.time())):
        self.packets['data'].append({
            'host'  : host,
            'key'   : key,
            'value' : val,
            'clock' : clock})

    def set_packet(self, host, key, val, clock=int(time.time())):
        data = [{
            'host'  : host,
            'key'   : key,
            'value' : val,
            'clock' : clock
            }]

        self.packets['data'] = data

    def get_packets(self, **args):
        return self.packets['data']

    def clean(self):
        self.packets = {'request': 'sender data', 'data': []}

    def send(self):
        data        = json.dumps(self.packets, ensure_ascii=False)
        data_bytes  = data.encode('utf-8')
        header      = b'ZBXD\x01'
        length      = struct.pack('<Q', len(data_bytes))
        packet      = header + length + data_bytes

        result      = {}
        response    = b''

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # send packet.
                sock.settimeout(30)
                sock.connect((self.zabbix, self.port))
                sock.sendall(packet)

                # receive response.
                while True:
                    chunk = sock.recv(1024)
                    if not chunk:
                        break
                    response += chunk

            # ZBXDZ{"response":"success","info":"processed: 1; failed: 0; total: 1; seconds spent: 0.000197"}
            response = response.decode('utf-8')

            # {"response":"success","info":"processed: 1; failed: 0; total: 1; seconds spent: 0.000197"}
            result   = json.loads(response[response.find('{'):])
        except Exception as e:
            raise e
        finally:
            pass

        return result

if __name__ == '__main__':
    # parse options
    parser = argparse.ArgumentParser(description='zabbix sender python implementation')
    parser.add_argument('-z', '--zabbix', action='store', dest='z', help='zabbix server address', default='localhost')
    parser.add_argument('-p', '--port', action='store', dest='p', help='zabbix server port', default=10051)
    parser.add_argument('-s', '--host', action='store', dest='s', help='managed hostname or address', required=True)
    parser.add_argument('-k', '--key', action='store', dest='k', help='item key', required=True)
    parser.add_argument('-o', '--value', action='store', dest='o', help='item value', required=True)
    args = parser.parse_args()

    sender = ZabbixSender(args.z, port=args.p)
    sender.set_packet(host=args.s, key=args.k, val=args.o)
    res = sender.send()
