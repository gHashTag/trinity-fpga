#!/usr/bin/env python3
"""Find the UART port the TRI-NET node answers on.

Board lookup is platform-dependent: the FT2232H's UART channel shows up as
usbserial-<something> whose name differs per machine and per cable order, and
the CP2102N dongle may or may not be present. So do not guess the port: probe
every /dev/cu.usbserial* (plus a --port override) at the fleet baud rates with
a MAC32 request and report which one answers with a 19-byte A5 frame.

A board that answers with status=0x04 (NO_KEY) still proves the port and rate;
set the key afterwards (see AGENT_BOARD_CHEATSHEET.md).

Usage:
    python3 discover_port.py                  # scan everything
    python3 discover_port.py --port /dev/cu.usbserial-XXXX
"""
import argparse
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    N_BYTES, OP_MAC32,
)

STATUS_NAME = {0x01: "keyed", 0x02: "KEY_SET", 0x03: "KEY_LOCKED", 0x04: "no key"}

BAUDS = [1144744, 1174465, 1123889, 160000, 115200]  # fleet rates + fallbacks
RESP_LEN = 19


def probe(ser, baud):
    ser.baudrate = baud
    ser.reset_input_buffer()
    req = (bytes([0xAA, 0x55, OP_MAC32]) + (0).to_bytes(4, "little")
           + bytes(N_BYTES) + bytes(N_BYTES) + bytes(1))
    ser.write(req)
    time.sleep(0.05)
    raw = ser.read(RESP_LEN)
    if len(raw) == RESP_LEN and raw[0] == 0xA5:
        return raw
    return None


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--port", default="", help="probe only this port")
    args = a.parse_args()

    import serial

    ports = [args.port] if args.port else sorted(glob.glob("/dev/cu.usbserial*"))
    if not ports:
        print("no /dev/cu.usbserial* ports at all - check the USB cable")
        return 1
    for p in ports:
        for baud in BAUDS:
            try:
                ser = serial.Serial(p, baud, timeout=0.4)
            except Exception as e:
                print(f"{p}: cannot open ({e})")
                break
            raw = probe(ser, baud)
            if raw:
                status = raw[2]
                print(f"HIT  {p} @ {baud}: status={status:#04x} "
                      f"({STATUS_NAME.get(status, '?')}) raw={raw.hex()}")
                ser.close()
                return 0
            ser.close()
        print(f"miss {p}")
    print("no board answered - flash a node bitstream first (pld load), then rerun")
    return 1


if __name__ == "__main__":
    sys.exit(main())
