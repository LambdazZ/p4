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
from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections


def writeTableRule(p4info_helper, switch, table_name, match_fields, action_name, action_params = None):
    table_entry = p4info_helper.buildTableEntry(
        table_name=table_name,
        match_fields=match_fields,
        action_name=action_name,
        action_params=action_params)
    switch.WriteTableEntry(table_entry)

def writeIpv4ForwardRule(p4info_helper, switch, dst_ip_addr, forward_mac_addr, forward_port, match_ip_field=32):
    writeTableRule(p4info_helper, switch, 
        table_name="MyIngress.ipv4table", 
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, match_ip_field)
        },
        action_name="MyIngress.ipv4_forward",
        action_params={
            "dstAddr": forward_mac_addr,
            "port": forward_port
        }
    )


def main(p4info_file_path, bmv2_file_path):
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        print("define ecn length")
        threshold_limit = int(input())
        # Create a switch connection object for s1 and s2;
        # this is backed by a P4Runtime gRPC connection.
        # Also, dump all P4Runtime messages sent to switch to given txt files.
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')
        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s3',
            address='127.0.0.1:50053',
            device_id=2,
            proto_dump_file='logs/s3-p4runtime-requests.txt')

        # Send master arbitration update message to establish this controller as
        # master (required by P4Runtime before performing any other write operation)
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()

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

        # s1 rules
        writeIpv4ForwardRule(p4info_helper, s1, dst_ip_addr="10.0.1.1", forward_mac_addr="08:00:00:00:01:01", forward_port=2)
        writeIpv4ForwardRule(p4info_helper, s1, dst_ip_addr="10.0.1.11", forward_mac_addr="08:00:00:00:01:11", forward_port=1)
        writeIpv4ForwardRule(p4info_helper, s1, dst_ip_addr="10.0.2.0", match_ip_field=24, forward_mac_addr="08:00:00:00:02:00", forward_port=3)
        writeIpv4ForwardRule(p4info_helper, s1, dst_ip_addr="10.0.3.0", match_ip_field=24, forward_mac_addr="08:00:00:00:03:00", forward_port=4)
        # s2 rules
        writeIpv4ForwardRule(p4info_helper, s2, dst_ip_addr="10.0.2.2", forward_mac_addr="08:00:00:00:02:02", forward_port=2)
        writeIpv4ForwardRule(p4info_helper, s2, dst_ip_addr="10.0.2.22", forward_mac_addr="08:00:00:00:02:22", forward_port=1)
        writeIpv4ForwardRule(p4info_helper, s2, dst_ip_addr="10.0.1.0", match_ip_field=24, forward_mac_addr="08:00:00:00:01:00", forward_port=3)
        writeIpv4ForwardRule(p4info_helper, s2, dst_ip_addr="10.0.3.0", match_ip_field=24, forward_mac_addr="08:00:00:00:03:00", forward_port=4)
        # s3 rules
        writeIpv4ForwardRule(p4info_helper, s3, dst_ip_addr="10.0.3.3", forward_mac_addr="08:00:00:00:03:03", forward_port=1)
        writeIpv4ForwardRule(p4info_helper, s3, dst_ip_addr="10.0.1.0", match_ip_field=24, forward_mac_addr="08:00:00:00:01:00", forward_port=2)
        writeIpv4ForwardRule(p4info_helper, s3, dst_ip_addr="10.0.2.0", match_ip_field=24, forward_mac_addr="08:00:00:00:02:00", forward_port=3)
        print("Installed IPv4 forward rules")
        
        # Install ecn rules
        writeTableRule(p4info_helper, s1, 
            table_name="MyEgress.judge_congestion", 
            match_fields={
                "standard_metadata.egress_port": 3
            },
            action_name="MyEgress.set_ecn_threshold",
            action_params={
                "threshold": threshold_limit
            }
        )
        writeTableRule(p4info_helper, s2, 
            table_name="MyEgress.judge_congestion", 
            match_fields={
                "standard_metadata.egress_port": 3
            },
            action_name="MyEgress.set_ecn_threshold",
            action_params={
                "threshold": threshold_limit
            }
        )


    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/ecn.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/ecn.json')
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
