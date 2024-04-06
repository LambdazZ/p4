#!/usr/bin/env python3
import socket
import sys

from scapy.all import (
    IP,
    UDP,
    Ether,
    Packet,
    bind_layers,
    get_if_hwaddr,
    get_if_list,
    sendp
)
from scapy.fields import *


def get_if():
    ifs=get_if_list()
    iface=None # "h1-eth0"
    for i in get_if_list():
        if "eth0" in i:
            iface=i
            break;
    if not iface:
        print("Cannot find eth0 interface")
        exit(1)
    return iface

class SourceRoute(Packet):
   fields_desc = [ BitField("bos", 0, 1),
                   BitField("port", 0, 15)]

bind_layers(Ether, SourceRoute, type=0x1234)
bind_layers(SourceRoute, SourceRoute, bos=0)
bind_layers(SourceRoute, IP, bos=1)

def main():
    if len(sys.argv) < 3:
        print('Usage: python3 send.py <destination> <type>')
        print('type can be either "ip" or "sr"')
        exit(1)

    addr = socket.gethostbyname(sys.argv[1])
    pkt_type = sys.argv[2]
    iface = get_if()
    print("sending on interface %s to %s" % (iface, str(addr)))

    if pkt_type == "ip":
        pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff')
        pkt = pkt / IP(dst=addr) / UDP(dport=4321, sport=1234)
        pkt.show2()
        sendp(pkt, iface=iface, verbose=False)
    elif pkt_type == "sr":
        while True:
            print()
            s = str(input('Type space separated port nums '
                              '(example: "2 3 2 2 1") or "q" to quit: '))
            if s == "q":
                break;
            print()

            i = 0
            pkt =  Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff');
            for p in s.split(" "):
                try:
                    pkt = pkt / SourceRoute(bos=0, port=int(p))
                    i = i+1
                except ValueError:
                    pass
            if pkt.haslayer(SourceRoute):
                pkt.getlayer(SourceRoute, i).bos = 1

            pkt = pkt / IP(dst=addr) / UDP(dport=4321, sport=1234)
            pkt.show2()
            sendp(pkt, iface=iface, verbose=False)
    else:
        print("Invalid packet type. It should be either 'ip' or 'sr'.")
        exit(1)

if __name__ == '__main__':
    main()