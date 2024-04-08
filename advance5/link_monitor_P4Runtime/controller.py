#!/usr/bin/env python3
import argparse
import os
import sys
from time import sleep

import grpc

# Import P4Runtime lib from parent utils dir
# Probably there's a better way of doing this.
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.switch import ShutdownAllSwitchConnections

def writeIpv4TableRules(p4info_helper, port, sw,
                     dst_eth_addr, dst_ip_addr):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, 32)
        },
        action_name="MyIngress.ipv4_forward",
        action_params={
            "dstAddr": dst_eth_addr,
            "port": port
        })
    sw.WriteTableEntry(table_entry)

def writeSwidTableRules(p4info_helper, swid, sw):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyEgress.swid",
        default_action= "true",
        action_name="MyEgress.set_swid",
        action_params={
            "swid": swid
        })
    sw.WriteTableEntry(table_entry)


def readTableRules(p4info_helper, sw):
    """
    Reads the table entries from all tables on the switch.

    :param p4info_helper: the P4Info helper
    :param sw: the switch connection
    """
    print('\n----- Reading tables rules for %s -----' % sw.name)
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            table_name = p4info_helper.get_tables_name(entry.table_id)
            print('%s: ' % table_name, end=' ')
            for m in entry.match:
                print(p4info_helper.get_match_field_name(table_name, m.field_id), end=' ')
                print('%r' % (p4info_helper.get_match_field_value(m),), end=' ')
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print('->', action_name, end=' ')
            for p in action.params:
                print(p4info_helper.get_action_param_name(action_name, p.param_id), end=' ')
                print('%r' % p.value, end=' ')
            print()

def printGrpcError(e):
    print("gRPC Error:", e.details(), end=' ')
    status_code = e.code()
    print("(%s)" % status_code.name, end=' ')
    traceback = sys.exc_info()[2]
    print("[%s:%d]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))

def main(p4info_file_path, bmv2_file_path):
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        # Create a switch connection object for s1, s2, s3, s4;
        # this is backed by a P4Runtime gRPC connection.
        # Also, dump all P4Runtime messages sent to switch to given txt files.
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-link-monitor-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-link-monitor-requests.txt')
        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s3',
            address='127.0.0.1:50053',
            device_id=2,
            proto_dump_file='logs/s3-link-monitor-requests.txt')
        s4 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s4',
            address='127.0.0.1:50054',
            device_id=3,
            proto_dump_file='logs/s4-link-monitor-requests.txt')

        # Send master arbitration update message to establish this controller as
        # master (required by P4Runtime before performing any other write operation)
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()
        s4.MasterArbitrationUpdate()

        # Install the P4 program on the switches
        s1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s1")
        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s2")
        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s3")
        s4.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s4")

        writeSwidTableRules(p4info_helper, swid=1, sw=s1)
        writeIpv4TableRules(p4info_helper, sw=s1, port=1,
                        dst_eth_addr="08:00:00:00:01:11", dst_ip_addr="10.0.1.1")
        writeIpv4TableRules(p4info_helper, sw=s1, port=2,
                        dst_eth_addr="08:00:00:00:02:22", dst_ip_addr="10.0.2.2")
        writeIpv4TableRules(p4info_helper, sw=s1, port=3,
                        dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.3.3")
        writeIpv4TableRules(p4info_helper, sw=s1, port=4,
                        dst_eth_addr="08:00:00:00:04:00", dst_ip_addr="10.0.4.4")
        
        writeSwidTableRules(p4info_helper, swid=2, sw=s2)
        writeIpv4TableRules(p4info_helper, sw=s2, port=4,
                        dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.1.1")
        writeIpv4TableRules(p4info_helper, sw=s2, port=3,
                        dst_eth_addr="08:00:00:00:04:00", dst_ip_addr="10.0.2.2")
        writeIpv4TableRules(p4info_helper, sw=s2, port=1,
                        dst_eth_addr="08:00:00:00:03:33", dst_ip_addr="10.0.3.3")
        writeIpv4TableRules(p4info_helper, sw=s2, port=2,
                        dst_eth_addr="08:00:00:00:04:44", dst_ip_addr="10.0.4.4")
                        
        writeSwidTableRules(p4info_helper, swid=3, sw=s3)
        writeIpv4TableRules(p4info_helper, sw=s3, port=1,
                        dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.1")
        writeIpv4TableRules(p4info_helper, sw=s3, port=1,
                        dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.2.2")
        writeIpv4TableRules(p4info_helper, sw=s3, port=2,
                        dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.3.3")
        writeIpv4TableRules(p4info_helper, sw=s3, port=2,
                        dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.4.4")
                        
        writeSwidTableRules(p4info_helper, swid=4, sw=s4)
        writeIpv4TableRules(p4info_helper, sw=s4, port=2,
                        dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.1")
        writeIpv4TableRules(p4info_helper, sw=s4, port=2,
                        dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.2.2")
        writeIpv4TableRules(p4info_helper, sw=s4, port=1,
                        dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.3.3")
        writeIpv4TableRules(p4info_helper, sw=s4, port=1,
                        dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.4.4")

        readTableRules(p4info_helper, s1)
        readTableRules(p4info_helper, s2)
        readTableRules(p4info_helper, s3)
        readTableRules(p4info_helper, s4)
       
    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LinkMonitor Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/link_monitor.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/link_monitor.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)