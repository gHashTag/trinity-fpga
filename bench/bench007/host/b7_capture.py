#!/usr/bin/env python3
"""Capture a UART stream from the board with host timestamps, and seal it.

    python3 b7_capture.py --tag probe --seconds 120
    python3 b7_capture.py --tag xor_active_r1 --seconds 90 --port /dev/cu.usbserial-120

    # when another program owns the serial port (e.g. drive_bpseq.py), stamp its stdout:
    python3 -u drive_bpseq.py /dev/cu.usbserial-120 | python3 b7_capture.py --stdin --tag xor_active_r1
    (-u matters: a piped Python stdout is block-buffered and every line would get the same timestamp)

Writes into --out (default ./raw):
    uart_<tag>_<UTC>.bin      exact bytes as received
    uart_<tag>_<UTC>.log      one line per received line: <unix_ns>\t<text>
    uart_<tag>_<UTC>.sha256   sha256 of both files (commit this with them)

B7 lines (the bench_meter format) are decoded live so you can see the clock and
step rate while it runs. Anything else (e.g. the XOR trainer's own output) is
logged verbatim and timestamped, which is what host-side step counting needs.

Needs: pip3 install pyserial
"""
import argparse
import glob
import hashlib
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from b7_format import parse_b7  # noqa: E402


def find_port():
    pats = ["/dev/cu.SLAB_USBtoUART*", "/dev/cu.usbserial-*", "/dev/ttyUSB*"]
    found = sorted({p for pat in pats for p in glob.glob(pat)})
    if len(found) == 1:
        return found[0]
    if not found:
        sys.exit("No USB-UART port found. Is the mini-USB (UART) cable in and the board powered?\n"
                 "On the AX7203 the UART is the CP2102 mini-USB port, not the JTAG cable.")
    sys.exit("Several ports found, pass one with --port:\n  " + "\n  ".join(found) +
             "\nThe repo's bench used the CP2102 at /dev/cu.usbserial-120; the JTAG cable's FTDI "
             "channel receives nothing (fpga/HARDWARE_REFERENCE.md).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--tag", required=True, help="e.g. probe, idle_r1, active_r1")
    ap.add_argument("--out", default="raw")
    ap.add_argument("--stdin", action="store_true", help="timestamp lines from stdin instead of a serial port")
    a = ap.parse_args()

    if a.stdin:
        port = "stdin"
    else:
        try:
            import serial  # pyserial
        except ImportError:
            sys.exit("pyserial missing: pip3 install pyserial")
        port = a.port or find_port()
    os.makedirs(a.out, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(a.out, f"uart_{a.tag}_{stamp}")
    fb, fl = open(base + ".bin", "wb"), open(base + ".log", "w", encoding="utf-8")
    fl.write(f"# port={port} baud={a.baud} tag={a.tag} start_utc={stamp} seconds={a.seconds}\n")

    print(f"capturing {port} @ {a.baud} for {a.seconds:.0f} s -> {base}.*   (Ctrl-C stops early)")
    if a.stdin:
        class _In:                                   # same read() interface as pyserial
            def read(self, n):
                line = sys.stdin.buffer.readline()
                if not line:
                    raise KeyboardInterrupt
                return line
            def close(self):
                pass
        s = _In()
    else:
        s = serial.Serial(port, a.baud, timeout=0.2)
        s.reset_input_buffer()
    t_end = time.monotonic() + a.seconds
    buf = b""
    n_lines = n_b7 = n_bad = 0
    try:
        while time.monotonic() < t_end:
            # read what is already buffered, else block for ONE byte: a fixed
            # read(4096) would wait out the whole timeout and stamp every line
            # up to 0.2 s late
            chunk = s.read(getattr(s, "in_waiting", 0) or 1)
            if not chunk:
                continue
            fb.write(chunk)
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                t_ns = time.time_ns()
                text = raw.rstrip(b"\r").decode("latin-1")
                fl.write(f"{t_ns}\t{text}\n")
                n_lines += 1
                if text.startswith("B7"):
                    rec = parse_b7(text)
                    if rec is None:
                        n_bad += 1
                        print(f"  bad B7 line (checksum/format): {text!r}")
                    else:
                        n_b7 += 1
                        seq, cyc, stp = rec
                        note = "  (window 0 is partial: ignored by the analysis)" if seq == 0 else ""
                        print(f"  seq {seq:5d}   clock {cyc / 1e6:11.6f} MHz   steps {stp:>10d} /s{note}")
                else:
                    print(f"  {text}")
    except KeyboardInterrupt:
        print("stopped")
    finally:
        s.close()
        fb.close()
        fl.close()

    with open(base + ".sha256", "w") as f:
        for ext in (".bin", ".log"):
            h = hashlib.sha256(open(base + ext, "rb").read()).hexdigest()
            f.write(f"{h}  {os.path.basename(base + ext)}\n")
    print(f"lines={n_lines}  B7 ok={n_b7}  B7 bad={n_bad}")
    print(f"sealed: {base}.sha256")
    if n_lines == 0:
        print("NOTHING RECEIVED. Check: bitstream loaded (DONE LED), right port, 115200 baud. "
              "For the probe: LED0 blinking = 200 MHz crystal path alive; LED1 = CFGMCLK alive.")


if __name__ == "__main__":
    main()
