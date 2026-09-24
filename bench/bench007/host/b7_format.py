"""The bench_meter line format, in one place, shared by capture and analysis.

    B7,SSSSSSSS,CCCCCCCC,PPPPPPPP,KK
    S seq, C DUT cycles in the window, P steps in the window (32-bit hex each)
    K = XOR of the 12 bytes of S, C, P (hex)
"""
import re

_B7 = re.compile(r"^B7,([0-9A-F]{8}),([0-9A-F]{8}),([0-9A-F]{8}),([0-9A-F]{2})$")


def _x4(w):
    return (w >> 24) ^ ((w >> 16) & 0xFF) ^ ((w >> 8) & 0xFF) ^ (w & 0xFF)


def checksum(seq, cyc, stp):
    return (_x4(seq) ^ _x4(cyc) ^ _x4(stp)) & 0xFF


def make_b7(seq, cyc, stp):
    """Encode a line exactly as the RTL does (used by the self-tests)."""
    return f"B7,{seq:08X},{cyc:08X},{stp:08X},{checksum(seq, cyc, stp):02X}"


def parse_b7(text):
    """(seq, cyc, stp) for a valid line, None for anything malformed or corrupted."""
    m = _B7.match(text.strip())
    if not m:
        return None
    seq, cyc, stp, k = (int(g, 16) for g in m.groups())
    if checksum(seq, cyc, stp) != k:
        return None
    return seq, cyc, stp
