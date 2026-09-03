#!/usr/bin/env bash
# vivado-nonet.sh — run vivado inside a rootless user+network namespace.
#
# WHY: Vivado 2026.1's Flexera RUI SDK telemetry (~/.Xilinx/Vivado/.RUISDK)
# phones home during write_bitstream with raw connect() calls that IGNORE the
# http_proxy/https_proxy environment (observed endpoints: 67.227.186.229:443,
# 72.52.161.233:443 — Flexera — and the cloud-metadata address
# 169.254.169.254:80). On this egress-filtered host those connects hang in
# SYN retries and Vivado books the wait into the timed write_bitstream phase
# (measured: bitgen_s 138-408 s for identical work; true value ~13 s).
# A proxy blackhole cannot stop a direct connect(); a network namespace can:
# inside `unshare -r -n` only loopback exists, connect() to any external
# address fails instantly with ENETUNREACH, and the run is hermetic.
#
# LICENSE: the FlexNet license (~/.Xilinx/Xilinx.lic, Basic tier) is
# node-locked to HOSTID=<host MAC>. Inside a fresh netns no interface carries
# that MAC, so the hostid check would fail. Fix (fully rootless, `-r` makes us
# root in-namespace): recreate the licensed MAC on a dummy interface (lic0)
# with NO external connectivity. The MAC is read from the HOSTID= field of the
# license file itself (fallback: enp5s0's address).
#
# Usage: vivado-nonet.sh <any vivado args>   (drop-in replacement for vivado)

set -eo pipefail

LIC_FILE="${XILINXD_LICENSE_FILE:-$HOME/.Xilinx/Xilinx.lic}"
LIC_MAC=""
if [ -r "$LIC_FILE" ]; then
    hostid="$(grep -oiE 'HOSTID=[0-9a-f]{12}' "$LIC_FILE" | head -1 | cut -d= -f2)"
    if [ -n "$hostid" ]; then
        LIC_MAC="$(echo "$hostid" | tr 'A-F' 'a-f' | sed 's/../&:/g; s/:$//')"
    fi
fi
if [ -z "$LIC_MAC" ]; then
    LIC_MAC="$(cat /sys/class/net/enp5s0/address 2>/dev/null || true)"
fi

exec env LIC_MAC="$LIC_MAC" unshare -r -n bash -c '
    ip link set lo up
    if [ -n "$LIC_MAC" ]; then
        ip link add lic0 type dummy 2>/dev/null \
          && ip link set lic0 address "$LIC_MAC" \
          && ip link set lic0 up
    fi
    exec "$@"' nonet vivado "$@"
