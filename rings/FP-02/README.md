# FP-02 — XVC Flasher

XVC (Xilinx Virtual Cable) WiFi JTAG flasher via ESP32 bridge.

## Protocol

XVC over TCP (port 2542): `getinfo:`, `shift:`, `settck:` commands.

## Flash Pipeline

```text
1. TCP connect to ESP32 XVC bridge (192.168.x.x:2542)
2. Verify IDCODE (0x0362D093 for XC7A200T)
3. Shift IR: JPROGRAM (0x01)
4. Shift DR: address + length + bitstream data
5. Shift IR: JSTART (0x07)
6. Shift IR: CFG_IN (0x3C) - DONE flag check
```

## Replaces

- `xvc_flash.sh`
- `AUTO_FLASH.sh`
- `flash.sh`

`phi^2 + 1/phi^2 = 3`
